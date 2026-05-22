"""
@module intent_agent
@description Intent 判斷代理。使用關鍵字規則（快速）+ LLM 分類（精準）雙層策略，
             根據使用者指令判斷任務意圖：summary | quiz | plan | full。
@dependencies core.llm_client
@author 沈靖恩（Agent / 核心邏輯）
@version 1.1.0
"""

import logging
import re
from typing import Literal

from core.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# ── Intent 型別別名 ───────────────────────────────────────────────────────────
IntentType = Literal["summary", "quiz", "plan", "full"]

# ── 關鍵字規則表（層一：快速判斷，無 LLM 費用）────────────────────────────────
KEYWORD_RULES: list[tuple[IntentType, list[str]]] = [
    ("full",    ["整理.*出題", "摘要.*測驗", "出題.*摘要", "總結.*選擇題", "總結.*出題", "摘要.*出題"]),
    ("plan",    ["複習計畫", "讀書計畫", "下週考試", "安排複習", "準備考試", "規劃"]),
    ("summary", ["整理重點", "摘要", "重點", "總結", "幫我整理"]),
    ("quiz",    ["出題", "選擇題", "測驗", "考題", "練習題", "是非題"]),
]

# ── LLM 分類 Prompt ───────────────────────────────────────────────────────────
INTENT_CLASSIFY_PROMPT = """
你是一個學習輔助系統的意圖分類器。
請判斷以下使用者指令屬於哪種任務類型，只能回答以下四個選項之一：

- summary：使用者想要整理重點或摘要講義內容
- quiz：使用者想要生成測驗題目
- plan：使用者想要獲得個人化複習計畫
- full：使用者同時想要摘要 + 出題（完整流程）

使用者指令：「{instruction}」

請只回答一個英文單詞（summary / quiz / plan / full），不要加任何解釋。
""".strip()


class IntentAgent:
    """
    Intent 判斷代理。

    採用雙層判斷策略：
    1. 關鍵字規則（< 1ms，無費用）：處理明確指令
    2. LLM 分類（~1s，消耗 Token）：處理模糊或複合指令

    Args:
        use_llm_fallback: 若關鍵字無法判斷，是否呼叫 LLM（預設 True）

    Example:
        >>> agent = IntentAgent()
        >>> intent = await agent.classify("幫我整理重點並出 3 題選擇題")
        >>> print(intent)  # 'full'
    """

    def __init__(self, use_llm_fallback: bool = True) -> None:
        self.use_llm_fallback = use_llm_fallback
        self._llm = get_llm_client()

    async def classify(self, instruction: str) -> IntentType:
        """
        判斷使用者指令的任務意圖。

        Args:
            instruction: 使用者輸入的自然語言指令

        Returns:
            IntentType: 'summary' | 'quiz' | 'plan' | 'full'
        """
        # 層一：關鍵字規則（優先）
        keyword_result = self._classify_by_keywords(instruction)
        if keyword_result is not None:
            logger.debug("[IntentAgent] 關鍵字判斷：%s → %s", instruction[:30], keyword_result)
            return keyword_result

        # 層二：LLM 分類（fallback）
        if self.use_llm_fallback:
            return await self._classify_by_llm(instruction)

        # 預設回傳 summary
        logger.warning("[IntentAgent] 無法判斷意圖，預設為 summary：%s", instruction[:30])
        return "summary"

    def _classify_by_keywords(self, instruction: str) -> IntentType | None:
        """
        使用正規表達式關鍵字規則判斷意圖。

        Args:
            instruction: 使用者指令

        Returns:
            IntentType | None: 判斷結果；無法判斷時回傳 None
        """
        for intent, patterns in KEYWORD_RULES:
            for pattern in patterns:
                if re.search(pattern, instruction):
                    return intent
        return None

    async def _classify_by_llm(self, instruction: str) -> IntentType:
        """
        使用 LLM 分類模糊指令（僅在關鍵字無法判斷時呼叫）。

        Args:
            instruction: 使用者指令

        Returns:
            IntentType: LLM 判斷的意圖類型
        """
        VALID_INTENTS = {"summary", "quiz", "plan", "full"}
        prompt = INTENT_CLASSIFY_PROMPT.format(instruction=instruction)
        try:
            response = await self._llm.complete(
                prompt=prompt,
                system_prompt="你是一個精確的意圖分類器，只回答指定選項之一。",
                temperature=0.0,
                max_tokens=10,
            )
            result = response.strip().lower()
            if result in VALID_INTENTS:
                logger.debug("[IntentAgent] LLM 判斷：%s → %s", instruction[:30], result)
                return result  # type: ignore
        except Exception as exc:
            logger.error("[IntentAgent] LLM 分類失敗：%s", exc)

        return "summary"  # 最終預設
