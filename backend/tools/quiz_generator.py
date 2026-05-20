"""
@module quiz_generator
@description 測驗題目生成工具。依據 RAG 段落與主題，呼叫 LLM 生成
             選擇題（四選一）或是非題，供學生作答評量。
@dependencies core.llm_client
@author 沈靖恩（Agent / 核心邏輯）
@version 1.1.0
"""

import json
import logging
import re

from core.llm_client import LLMClient

logger = logging.getLogger(__name__)

# ── 出題 Prompt 模板 ──────────────────────────────────────────────────────────
QUIZ_PROMPT = """
你是一位專業的學習評量設計師。請根據以下講義段落，用繁體中文出 {count} 題{question_type_label}。

每題必須包含：
- 題目（question）
- 四個選項（options，列表）
- 正確答案（correct_answer，對應選項的完整文字）
- 解析說明（explanation，2–3 句）
- 對應主題（topic）

請以 JSON 陣列格式回應，範例：
[
  {{
    "topic": "TF-IDF",
    "question": "TF-IDF 中 IDF 代表什麼？",
    "options": ["詞頻", "逆文件頻率", "文件頻率", "詞向量"],
    "correct_answer": "逆文件頻率",
    "explanation": "IDF（Inverse Document Frequency）衡量一個詞的稀有程度。..."
  }}
]

講義段落：
{context}

主題：{topic}
""".strip()


class QuizGenerator:
    """
    測驗題目生成工具。

    Args:
        llm_client: LLM 客戶端
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def generate(
        self,
        passages: list[dict],
        topic: str,
        count: int = 3,
        question_type: str = "multiple_choice",
        provider: str | None = None,
    ) -> list[dict]:
        """
        根據 RAG 段落生成測驗題目。

        Args:
            passages: RAG 檢索段落列表
            topic: 題目主題（如「TF-IDF」）
            count: 生成題數（預設 3，最多 10）
            question_type: 題型（'multiple_choice' | 'true_false'）
            provider: LLM 供應商

        Returns:
            list[dict]: 題目列表，每題包含：
                topic, question, options, correct_answer, explanation
        """
        count = min(max(count, 1), 10)  # 限制 1–10 題

        if not passages:
            logger.warning("[QuizGen] 段落為空，無法出題")
            return []

        # 合併相關段落（最多取 3 筆）
        top_passages = sorted(passages, key=lambda p: p["score"], reverse=True)[:3]
        context = "\n\n---\n\n".join(p["text"] for p in top_passages)

        type_label = "選擇題（四選一）" if question_type == "multiple_choice" else "是非題"
        prompt = QUIZ_PROMPT.format(
            count=count,
            question_type_label=type_label,
            context=context,
            topic=topic,
        )

        try:
            raw = await self._llm.complete(
                prompt=prompt,
                temperature=0.5,
                max_tokens=2048,
                provider=provider,
            )
            questions = self._parse_questions(raw)
            # 補齊 topic 欄位
            for q in questions:
                q.setdefault("topic", topic)
                q.setdefault("question_type", question_type)
            logger.info("[QuizGen] 生成 %d 題（主題：%s）", len(questions), topic)
            return questions
        except Exception as exc:
            logger.error("[QuizGen] 題目生成失敗：%s", exc)
            return []

    def _parse_questions(self, raw: str) -> list[dict]:
        """解析 LLM 返回的 JSON 題目陣列，容忍格式異常。"""
        # 嘗試提取 ```json ... ``` 或 [ ... ]
        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if match:
            raw = match.group(1)
        else:
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                raw = match.group(0)

        try:
            questions = json.loads(raw)
            if isinstance(questions, list):
                return questions
        except json.JSONDecodeError:
            logger.warning("[QuizGen] JSON 解析失敗，返回空列表")
        return []
