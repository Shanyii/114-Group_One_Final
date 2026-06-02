"""
@module plan_generator
@description 個人化複習計畫生成工具（Step 7）。依據學生弱點 Map 與考試日期，
             呼叫 LLM 生成優先順序明確的複習建議。
@dependencies core.llm_client
@author 沈靖恩（Agent / 核心邏輯）
@version 1.1.0
"""

import json
import logging
import re

from core.llm_client import LLMClient

logger = logging.getLogger(__name__)

PLAN_PROMPT = """
你是一位專業的學習計畫顧問。請根據學生的弱點分析，用繁體中文生成個人化複習計畫。

學生弱點（主題：錯誤次數）：
{weak_topics_str}

考試日期：{exam_date}

請生成複習建議，以 JSON 格式回應：
{{
  "recommendations": [
    {{
      "topic": "主題名稱",
      "priority": "high / medium / low",
      "reason": "為何需要優先複習",
      "suggested_actions": ["具體行動 1", "具體行動 2"]
    }}
  ],
  "estimated_study_hours": 預估總複習時數（數字）,
  "summary": "整體複習策略摘要（2–3 句）"
}}

依錯誤次數多的主題給予 high 優先級，少的給 medium/low。
若無弱點資料，請給予鼓勵並建議全面複習。
""".strip()


class PlanGenerator:
    """
    個人化複習計畫生成工具。

    Args:
        llm_client: LLM 客戶端
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def generate(
        self,
        weak_topics: dict[str, int],
        exam_date: str | None = None,
        provider: str | None = None,
    ) -> dict:
        """
        根據弱點 Map 生成個人化複習計畫。

        Args:
            weak_topics: 弱點主題字典，如 {'TF-IDF': 2, 'PCFG': 3}
            exam_date: 考試日期字串（ISO 8601），可選
            provider: LLM 供應商

        Returns:
            dict: 複習計畫，包含：
                recommendations, estimated_study_hours, summary
        """
        if not weak_topics:
            logger.info("[PlanGen] 無弱點資料，生成通用建議")
            weak_topics_str = "（尚無答題紀錄，建議全面複習）"
        else:
            # 依錯誤次數降序排列
            sorted_topics = sorted(weak_topics.items(), key=lambda x: x[1], reverse=True)
            weak_topics_str = "\n".join(
                f"• {topic}：答錯 {count} 次" for topic, count in sorted_topics
            )

        prompt = PLAN_PROMPT.format(
            weak_topics_str=weak_topics_str,
            exam_date=exam_date or "未指定",
        )

        try:
            raw = await self._llm.complete(
                prompt=prompt,
                temperature=0.4,
                max_tokens=1024,
                provider=provider,
            )
            plan = self._parse_plan(raw)
            logger.info("[PlanGen] 複習計畫生成完成，建議項目：%d", len(plan.get("recommendations", [])))
            return plan
        except Exception as exc:
            logger.error("[PlanGen] 計畫生成失敗：%s", exc)
            return {
                "recommendations": [],
                "estimated_study_hours": 0,
                "summary": f"計畫生成失敗：{exc}",
            }

    def _parse_plan(self, raw: str) -> dict:
        """解析 LLM 返回的計畫 JSON。"""
        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if match:
            raw = match.group(1)
        else:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                raw = match.group(0)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[PlanGen] JSON 解析失敗，使用原始文字")
            return {
                "recommendations": [],
                "estimated_study_hours": 0,
                "summary": raw.strip(),
            }
