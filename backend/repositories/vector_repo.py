"""
@module vector_repo
@description ChromaDB 向量索引 Repository（ADR-003：跨 Session 持久化）。
             使用 PersistentClient 模式，同一份講義上傳後無需重複建索引。
             提供文件索引、語意查詢兩個主要介面。
@dependencies chromadb, core.config, core.llm_client
@author 楊沁霖（RAG / 資料處理）/ 黃柏豪（整合）
@version 1.1.0
"""
from __future__ import annotations

import logging
import uuid
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from core.config import get_settings
from core.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# ChromaDB 集合名稱
COLLECTION_NAME = "lecture_chunks"

# 每個 Chunk 的 Embedding 維度（text-embedding-004 = 768）
EMBEDDING_DIMENSION = 768


class VectorRepository:
    """
    ChromaDB 向量索引 Repository。

    使用 PersistentClient 本地持久化（ADR-003），
    避免每次啟動重複 Embedding 費用。

    集合名稱：lecture_chunks
    metadata 欄位：document_id, student_id, chunk_index
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.top_k = settings.rag_top_k
        self._llm_client = get_llm_client()

        # 使用 PersistentClient（ADR-003：跨 Session 保留索引）
        self._client = chromadb.PersistentClient(
            path=settings.chroma_db_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # 使用 Cosine 相似度
        )
        logger.info(
            "[VectorRepo] ChromaDB 初始化完成，集合大小：%d", self._collection.count()
        )

    # ── 索引建立 ──────────────────────────────────────────────────────────────

    async def index_document(
        self,
        document_id: str,
        student_id: str,
        chunks: list[str | dict],
    ) -> int:
        """
        將文件的 Chunk 列表建立向量索引。

        若相同 document_id 已存在索引，先刪除舊索引再重建（避免重複）。

        Args:
            document_id: 文件 UUID
            student_id: 學生 UUID
            chunks: 文字 Chunk 列表（可為字串列表或含有 text 與 page_num 的字典列表）

        Returns:
            int: 成功建立索引的 Chunk 數量
        """
        if not chunks:
            logger.warning("[VectorRepo] 空白 Chunks，跳過索引：%s", document_id)
            return 0

        # 刪除同一文件的舊索引
        await self.delete_document(document_id)

        # 批次 Embedding（避免單次太多 Token）
        BATCH_SIZE = 10
        ids, embeddings, documents, metadatas = [], [], [], []

        for i, chunk in enumerate(chunks):
            try:
                # 兼容處理：支援字串列表或字典列表
                if isinstance(chunk, dict):
                    chunk_text = chunk.get("text", "")
                    page_num = chunk.get("page_num")
                else:
                    chunk_text = chunk
                    page_num = None

                if not chunk_text or not chunk_text.strip():
                    continue

                embedding = await self._llm_client.embed(chunk_text)
                chunk_id = f"{document_id}_{i}"
                ids.append(chunk_id)
                embeddings.append(embedding)
                documents.append(chunk_text)
                
                metadata = {
                    "document_id": document_id,
                    "student_id": student_id,
                    "chunk_index": i,
                }
                if page_num is not None:
                    metadata["page_num"] = page_num
                
                metadatas.append(metadata)
            except Exception as exc:
                logger.error("[VectorRepo] Chunk %d Embedding 失敗：%s", i, exc)
                continue

            # 批次寫入 ChromaDB
            if len(ids) >= BATCH_SIZE:
                self._collection.add(
                    ids=ids, embeddings=embeddings,
                    documents=documents, metadatas=metadatas,
                )
                ids, embeddings, documents, metadatas = [], [], [], []

        # 寫入剩餘批次
        if ids:
            self._collection.add(
                ids=ids, embeddings=embeddings,
                documents=documents, metadatas=metadatas,
            )

        count = len(chunks)
        logger.info("[VectorRepo] 索引建立完成：document_id=%s, chunks=%d", document_id, count)
        return count

    async def delete_document(self, document_id: str) -> None:
        """
        刪除指定文件的所有 Chunk 索引。

        Args:
            document_id: 文件 UUID
        """
        try:
            self._collection.delete(where={"document_id": document_id})
            logger.debug("[VectorRepo] 已刪除舊索引：%s", document_id)
        except Exception as exc:
            logger.warning("[VectorRepo] 刪除索引失敗（可能不存在）：%s", exc)

    # ── 語意查詢 ──────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        document_id: str | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        """
        語意查詢相關段落（RAG Retrieval）。

        Args:
            query: 查詢字串（使用者問題或關鍵字）
            document_id: 限定查詢的文件 UUID（None 則跨文件搜尋）
            top_k: 返回最大段落數（None 則使用 settings.rag_top_k）

        Returns:
            list[dict]: 相關段落列表，每項包含：
                - text: 段落文字
                - score: 相似度分數（0–1，越高越相關）
                - chunk_index: Chunk 序號
                - document_id: 來源文件 ID
        """
        k = top_k or self.top_k
        query_embedding = await self._llm_client.embed_query(query)

        where_filter = None
        if document_id:
            where_filter = {"document_id": document_id}

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(k, max(self._collection.count(), 1)),
                where=where_filter,
                include=["documents", "distances", "metadatas"],
            )
        except Exception as exc:
            logger.error("[VectorRepo] 查詢失敗：%s", exc)
            return []

        passages = []
        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        for doc, dist, meta in zip(docs, distances, metadatas):
            # ChromaDB Cosine 距離 → 相似度（越小越相似）
            score = max(0.0, 1.0 - dist)
            passages.append({
                "text": doc,
                "score": round(score, 4),
                "chunk_index": meta.get("chunk_index", -1),
                "document_id": meta.get("document_id", ""),
                "page_num": meta.get("page_num") if meta else None,
            })

        logger.debug("[VectorRepo] 查詢完成：query='%s', 返回 %d 段落", query[:30], len(passages))
        return passages

    def get_collection_size(self) -> int:
        """回傳向量集合中的 Chunk 總數。"""
        return self._collection.count()


@lru_cache(maxsize=1)
def get_vector_repo() -> VectorRepository:
    """取得 VectorRepository 單例。"""
    return VectorRepository()
