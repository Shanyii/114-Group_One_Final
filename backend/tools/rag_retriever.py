"""
@module rag_retriever
@description RAG 語意檢索工具。結合 ChromaDB 向量查詢（語意相似度）與
             關鍵字過濾，返回最相關的講義段落供 LLM 生成摘要或題目。
@dependencies repositories.vector_repo, core.llm_client
@author 楊沁霖（RAG / 資料處理）
@version 1.1.0
"""

import logging
import re

from core.llm_client import LLMClient
from repositories.vector_repo import VectorRepository

logger = logging.getLogger(__name__)

# ── 最低相似度門檻（低於此值的段落視為不相關）────────────────────────────────
MIN_SIMILARITY_SCORE = 0.3


class RAGRetriever:
    """
    RAG 語意檢索工具。

    步驟：
    1. 從使用者指令中提取核心查詢主題（關鍵字萃取）
    2. 呼叫 VectorRepository 進行向量語意查詢
    3. 過濾低相關度段落（score < MIN_SIMILARITY_SCORE）
    4. 返回排序後的相關段落列表

    Args:
        vector_repo: ChromaDB 向量 Repository
        llm_client: LLM 客戶端（用於查詢改寫）
    """

    def __init__(self, vector_repo: VectorRepository, llm_client: LLMClient) -> None:
        self._vector_repo = vector_repo
        self._llm = llm_client

    async def retrieve(
        self,
        instruction: str,
        document_id: str,
        top_k: int | None = None,
    ) -> list[dict]:
        """
        根據使用者指令檢索最相關的講義段落。

        Args:
            instruction: 使用者指令（如「幫我整理 TF-IDF 的重點」）
            document_id: 要查詢的文件 UUID
            top_k: 最多返回段落數（None 則使用設定值）

        Returns:
            list[dict]: 相關段落列表，每項包含：
                - text: 段落文字
                - score: 相似度（0–1）
                - chunk_index: 段落序號
        """
        # 從指令中萃取查詢主題（用於語意搜尋）
        query = self._extract_query(instruction)
        logger.debug("[RAGRetriever] 查詢主題：%s（原始：%s）", query, instruction[:40])

        # 向量語意查詢
        passages = await self._vector_repo.search(
            query=query,
            document_id=document_id,
            top_k=top_k,
        )

        # 過濾低相關度段落
        filtered = [p for p in passages if p["score"] >= MIN_SIMILARITY_SCORE]
        if not filtered and passages:
            # 若全部低於門檻，至少保留最高分的 1 筆
            filtered = [passages[0]]
            logger.warning("[RAGRetriever] 所有段落相似度偏低，保留最佳 1 筆（score=%.3f）", passages[0]["score"])

        logger.info("[RAGRetriever] 檢索完成：查詢='%s', 返回 %d/%d 段落", query, len(filtered), len(passages))
        return filtered

    def _extract_query(self, instruction: str) -> str:
        """
        從使用者指令中萃取核心查詢主題。

        簡單規則：移除動詞指令字首（幫我整理、出題、複習等），
        保留主題關鍵字。

        Args:
            instruction: 使用者原始指令

        Returns:
            str: 提取的查詢字串
        """
        # 移除常見動詞前綴
        PREFIXES_TO_REMOVE = [
            r"^幫我(整理|摘要|出題|複習|解釋|說明)?",
            r"^請(幫我|你)?(整理|摘要|出題|複習)?",
            r"^我想(要|了解|知道)?",
        ]
        query = instruction
        for pattern in PREFIXES_TO_REMOVE:
            query = re.sub(pattern, "", query).strip()

        # 移除題數等修飾詞
        query = re.sub(r"\d+\s*題", "", query).strip()
        query = re.sub(r"(選擇題|是非題|填空題|出題|測驗)", "", query).strip()

        # 若萃取後為空，使用原始指令
        if not query:
            query = instruction

        return query[:200]  # 限制長度
