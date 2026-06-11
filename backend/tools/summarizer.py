"""
@module summarizer
@description 重點摘要生成工具。將 RAG 檢索到的段落傳入 LLM，
             生成結構化的章節重點摘要與條列式重點。
@dependencies core.llm_client
@author 沈靖恩（Agent / 核心邏輯）
@version 1.1.0
"""

from __future__ import annotations

import json
import logging
import re

from core.llm_client import LLMClient

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """
你是一位專業的學習輔助 AI。請根據以下講義內容，用繁體中文整理出：
1. 整份講義的核心概念摘要：請提供非常詳盡、結構完整的摘要（字數至少 500-1000 字，分段清晰，不設上限）。必須深入涵蓋整篇講義的完整背景脈絡、核心大綱、章節之間的關聯性，以及關鍵結論。切勿過於精簡，請盡可能保留所有重要的細節與知識脈絡。
2. 詳細的條列式重點：請提供 8-15 個涵蓋全篇的詳細條列式重點，用「•」開頭。每個重點均需包含完整的背景脈絡、核心原理說明、公式或理論依據（若有）與具體實例，絕對避免使用過於精簡的字句，每個重點字數應在 100-250 字之間，以保證足夠的學習細節，幫助學生完全理解講義中的複雜概念。
3. 核心名詞/專業術語與生詞清單（用於製作學習閃卡）：請特別擷取講義中「不常出現、較為生僻或較難懂」的專有名詞、生詞與核心概念，避免挑選太過普通或常識性的詞彙。數量請根據講義的難易度與長度動態調整（若講義內容較長或較難，應抓出 8 至 15 個；若內容極短或簡單，最少 5 個）。每個詞彙的定義（def）必須包含詳細的定義說明，以及在該講義上下文中的具體應用解釋。

請以 JSON 格式回應，格式如下：
{{
  "summary": "詳細核心概念摘要（至少 500-1000 字，分段清晰，涵蓋完整脈絡與背景）...",
  "key_points": [
    "• 重點一（請提供詳盡背景脈絡、核心原理與實例，100-250 字）",
    "• 重點二（請提供詳盡背景脈絡、核心原理與實例，100-250 字）",
    ...
  ],
  "glossary": [
    {{"term": "專有名詞/生僻詞一", "def": "詳細定義與在講義上下文中的具體應用解釋"}},
    {{"term": "專有名詞/生僻詞二", "def": "詳細定義與在講義上下文中的具體應用解釋"}},
    ...
  ]
}}

講義內容：
{context}

主題（若有）：{topic}
""".strip()


class Summarizer:
    """
    重點摘要生成工具。

    Args:
        llm_client: LLM 客戶端
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def summarize(
        self,
        passages: list[dict],
        topic: str = "",
        provider: str | None = None,
    ) -> dict:
        """
        根據 RAG 檢索段落生成重點摘要（保留供向下相容使用）。
        """
        if not passages:
            logger.warning("[Summarizer] 段落為空，回傳空摘要")
            return {"topic": topic, "summary": "無相關內容", "key_points": [], "glossary": []}

        # 合併段落（依相似度排序，取前 3 筆避免 Token 超限）
        top_passages = sorted(passages, key=lambda p: p["score"], reverse=True)[:3]
        context = "\n\n---\n\n".join(p["text"] for p in top_passages)
        return await self.summarize_text(context, topic, provider)

    async def summarize_text(
        self,
        text: str,
        topic: str = "",
        provider: str | None = None,
    ) -> dict:
        """
        根據完整講義文字內容生成完整的重點摘要與核心詞彙。
        """
        if not text or text == "無相關內容":
            return {"topic": topic, "summary": "無相關內容", "key_points": [], "glossary": []}

        prompt = SUMMARIZE_PROMPT.format(context=text, topic=topic or "（未指定）")

        try:
            raw = await self._llm.complete(
                prompt=prompt,
                temperature=0.3,
                max_tokens=4096,
                provider=provider,
                is_json=True,
            )
            result = self._parse_json_response(raw)
            result["topic"] = topic
            logger.info("[Summarizer] 完整摘要生成完成，詞彙數：%d", len(result.get("glossary", [])))
            return result
        except Exception as exc:
            logger.error("[Summarizer] 完整摘要生成失敗：%s", exc)
            return {"topic": topic, "summary": f"摘要生成失敗：{exc}", "key_points": [], "glossary": []}

    def _parse_json_response(self, raw: str) -> dict:
        """解析 LLM 返回的 JSON，並使用 safe_json_loads 容忍截斷或格式異常。"""
        from core.json_helper import safe_json_loads
        res = safe_json_loads(raw, default_factory=dict)
        if isinstance(res, dict):
            # 補齊預設值
            res.setdefault("summary", "")
            res.setdefault("key_points", [])
            res.setdefault("glossary", [])
            return res
        return {"summary": str(raw), "key_points": [], "glossary": []}
