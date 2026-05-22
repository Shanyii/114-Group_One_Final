"""
@module summarizer
@description 重點摘要生成工具。將 RAG 檢索到的段落傳入 LLM，
             生成結構化的章節重點摘要與條列式重點。
@dependencies core.llm_client
@author 沈靖恩（Agent / 核心邏輯）
@version 1.1.0
"""

import json
import logging
import re

from core.llm_client import LLMClient

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """
你是一位專業的學習輔助 AI。請根據以下講義段落，用繁體中文整理出：
1. 本段落的核心概念摘要（2–4 句話）
2. 5 個條列式重點（用「•」開頭）

請以 JSON 格式回應，格式如下：
{{
  "summary": "核心概念摘要...",
  "key_points": ["• 重點一", "• 重點二", "• 重點三", "• 重點四", "• 重點五"]
}}

講義段落：
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
        根據 RAG 檢索段落生成重點摘要。

        Args:
            passages: RAG 檢索返回的段落列表（含 text、score）
            topic: 主題名稱（可選，用於引導摘要方向）
            provider: LLM 供應商（None 則使用預設）

        Returns:
            dict: 摘要結果，包含：
                - topic: 主題
                - summary: 核心概念摘要
                - key_points: 條列式重點列表
        """
        if not passages:
            logger.warning("[Summarizer] 段落為空，回傳空摘要")
            return {"topic": topic, "summary": "無相關內容", "key_points": []}

        # 合併段落（依相似度排序，取前 3 筆避免 Token 超限）
        top_passages = sorted(passages, key=lambda p: p["score"], reverse=True)[:3]
        context = "\n\n---\n\n".join(p["text"] for p in top_passages)

        prompt = SUMMARIZE_PROMPT.format(context=context, topic=topic or "（未指定）")

        try:
            raw = await self._llm.complete(
                prompt=prompt,
                temperature=0.3,
                max_tokens=1024,
                provider=provider,
                is_json=True,
            )
            result = self._parse_json_response(raw)
            result["topic"] = topic
            logger.info("[Summarizer] 摘要生成完成，字數：%d", len(result.get("summary", "")))
            return result
        except Exception as exc:
            logger.error("[Summarizer] 摘要生成失敗：%s", exc)
            return {"topic": topic, "summary": f"摘要生成失敗：{exc}", "key_points": []}

    def _parse_json_response(self, raw: str) -> dict:
        """解析 LLM 返回的 JSON，容忍格式不完整的情況。"""
        # 原生 JSON 模式應該已經回傳乾淨的 JSON，但預防萬一還是保留 markdown 去除
        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if match:
            raw = match.group(1)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[Summarizer] JSON 解析失敗，使用原始文字")
            return {"summary": raw.strip(), "key_points": []}
