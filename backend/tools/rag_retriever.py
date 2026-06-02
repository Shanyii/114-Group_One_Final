"""
@module rag_retriever
@description RAG 語意檢索工具。結合 ChromaDB 向量查詢（語意相似度）與
             關鍵字過濾，返回最相關的講義段落供 LLM 生成摘要或題目。
@dependencies repositories.vector_repo, core.llm_client
@author 楊沁霖（RAG / 資料處理）
@version 1.1.0
"""

from __future__ import annotations

import logging
import re

from core.llm_client import LLMClient
from repositories.vector_repo import VectorRepository

logger = logging.getLogger(__name__)

# ── 最低相似度門檻（低於此值的段落視為不相關）────────────────────────────────
MIN_SIMILARITY_SCORE = 0.3

# ── 混合檢索超參數 ────────────────────────────────────────────────────────
HYBRID_ALPHA = 0.7  # 向量分數權重，1 - HYBRID_ALPHA 為關鍵字分數權重


class RAGRetriever:
    """
    RAG 語意與關鍵字混合檢索工具。

    步驟：
    1. 呼叫 LLM 重寫/提煉核心查詢主題（當為 mock 模式或失敗時降級為 Regex）
    2. 呼叫 VectorRepository 查詢候選向量段落（擴大候選池）
    3. 對候選段落進行混合評分（結合向量相似度與關鍵字匹配度）與重排（Reranking）
    4. 過濾低相關度段落，返回前 top_k 個最相關的段落
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
                - score: 混合相似度分數（0–1）
                - chunk_index: 段落序號
                - document_id: 來源文件 ID
                - page_num: 來源頁碼
        """
        # 1. 從指令中提煉/重寫查詢主題（用於向量搜尋與關鍵字匹配）
        query = await self._extract_query(instruction)
        logger.debug("[RAGRetriever] 查詢主題：%s（原始：%s）", query, instruction[:40])

        target_k = top_k or self._vector_repo.top_k
        # 為了進行 Hybrid Rerank，我們向向量庫獲取較寬的候選範圍（3 倍，最少 10 個）
        candidate_k = max(target_k * 3, 10)

        # 2. 向量語意查詢候選段落
        passages = await self._vector_repo.search(
            query=query,
            document_id=document_id,
            top_k=candidate_k,
        )

        if not passages:
            logger.info("[RAGRetriever] 向量檢索結果為空：查詢='%s'", query)
            return []

        # 3. 混合評分（Hybrid Scoring）與重排（Reranking）
        hybrid_passages = []
        for p in passages:
            vector_score = p["score"]
            keyword_score = self._calculate_keyword_score(p["text"], query)

            # 結合向量語意相似度與關鍵字字面匹配率
            hybrid_score = HYBRID_ALPHA * vector_score + (1.0 - HYBRID_ALPHA) * keyword_score

            p["score"] = round(hybrid_score, 4)
            p["vector_score"] = vector_score
            p["keyword_score"] = round(keyword_score, 4)
            hybrid_passages.append(p)

        # 依 Hybrid Score 由高到低排序
        hybrid_passages.sort(key=lambda x: x["score"], reverse=True)

        # 4. 門檻過濾
        filtered = [p for p in hybrid_passages if p["score"] >= MIN_SIMILARITY_SCORE]
        if not filtered and hybrid_passages:
            # 若全部低於門檻，至少保留最高分的 1 筆
            filtered = [hybrid_passages[0]]
            logger.warning(
                "[RAGRetriever] 所有段落混合評分偏低，保留最佳 1 筆（score=%.3f）",
                hybrid_passages[0]["score"]
            )

        # 5. 截斷返回 top_k 筆
        result = filtered[:target_k]

        logger.info(
            "[RAGRetriever] 檢索完成：查詢='%s', 候選 %d 個, 最終返回 %d/%d 段落",
            query, len(passages), len(result), len(hybrid_passages)
        )
        return result

    async def _extract_query(self, instruction: str) -> str:
        """
        從使用者指令中萃取或重寫核心查詢主題。
        如果 llm_provider 為 mock，則使用 Regex 進行快速清理。
        否則，呼叫 LLM 進行查詢重寫與提煉。
        """
        if self._llm.settings.llm_provider == "mock":
            return self._regex_extract_query(instruction)

        try:
            prompt = (
                f"學生的指令是：\"{instruction}\"\n"
                f"請幫我分析學生的指令，並從中提取或重寫出適合用來在課程講義中進行「語意檢索」的核心查詢關鍵字詞或主題。\n"
                f"注意：\n"
                f"1. 必須移除無關的動詞和修飾語，例如「幫我整理」、「請出題考我」、「想了解」、「幫我解釋」、「是非題」等。\n"
                f"2. 只保留具體的核心學術名詞、概念或主題（例如「有限狀態自動機」、「TF-IDF」）。\n"
                f"3. 請直接輸出重寫後的查詢詞，嚴禁包含任何引號、前言、解釋或額外格式。"
            )

            rewritten_query = await self._llm.complete(
                prompt=prompt,
                system_prompt="你是一個 RAG 系統的查詢詞重寫與提煉專家。請直接回覆重寫後的關鍵字或查詢主題，不做任何額外說明。",
                temperature=0.0,
                max_tokens=100
            )
            rewritten = rewritten_query.strip()

            # 去除引號或書名號包裹
            for char in ['"', "'", '「', '」', '`']:
                if rewritten.startswith(char) and rewritten.endswith(char):
                    rewritten = rewritten[1:-1].strip()

            if rewritten:
                return rewritten[:200]
        except Exception as e:
            logger.error("[RAGRetriever] LLM 查詢重寫失敗，將使用 Regex fallback: %s", e)

        return self._regex_extract_query(instruction)

    def _regex_extract_query(self, instruction: str) -> str:
        """使用正則表達式進行基礎的指令過濾（Fallback / Mock 模式使用）。"""
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

        return query[:200]

    def _calculate_keyword_score(self, text: str, query: str) -> float:
        """
        計算關鍵字匹配分數。
        將查詢詞切分成中文字元與英文單字，並計算其在段落中出現的比例（Jaccard 匹配率）。
        """
        if not query or not text:
            return 0.0

        query_lower = query.lower()
        text_lower = text.lower()

        # 提取查詢詞中的 tokens (英文單字 + 中文字元，排除空格及標點)
        tokens = []

        # 英文單字/數字
        eng_tokens = re.findall(r'[a-zA-Z0-9]+', query_lower)
        tokens.extend(eng_tokens)

        # 中文字元（排除標點與特殊字元，中文字元範圍一般是 \u4e00-\u9fff）
        chi_chars = [c for c in query_lower if '\u4e00' <= c <= '\u9fff']
        tokens.extend(chi_chars)

        # 去重，避免重複字元/單字重複加權
        unique_tokens = list(set(tokens))

        if not unique_tokens:
            return 0.0

        # 計算有多少比例 of unique_tokens 存在於 text 中
        match_count = sum(1 for t in unique_tokens if t in text_lower)
        return match_count / len(unique_tokens)
