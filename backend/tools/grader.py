"""
@module grader
@description 答案批改工具（Step 5）。呼叫 LLM 比對學生答案與正確答案，
             提供批改結果與概念解析，並觸發學習狀態更新。
@dependencies core.llm_client, repositories.state_repo
@author 沈靖恩（Agent / 核心邏輯）
@version 1.1.0
"""

import json
import logging
import re
import uuid
from datetime import datetime

import aiosqlite

from core.config import get_settings
from core.llm_client import LLMClient
from repositories.state_repo import StateRepository

logger = logging.getLogger(__name__)

GRADE_PROMPT = """
你是一位嚴謹的學習評量老師。請判斷學生的作答是否正確，並提供詳細解析。

題目：{question}
正確答案：{correct_answer}
學生作答：{student_answer}

請以 JSON 格式回應：
{{
  "is_correct": true 或 false,
  "explanation": "2–3 句解析，說明正確概念及學生答錯的原因（若答錯）"
}}
""".strip()


class Grader:
    """
    答案批改工具。

    批改後自動呼叫 StateRepository 更新弱點記憶（step 6 的邏輯內嵌）。

    Args:
        llm_client: LLM 客戶端
        state_repo: 學習狀態 Repository
    """

    def __init__(self, llm_client: LLMClient, state_repo: StateRepository) -> None:
        self._llm = llm_client
        self._state_repo = state_repo
        self._settings = get_settings()

    async def grade_all(
        self,
        task_id: str,
        student_id: str,
        answers: list[dict],
        provider: str | None = None,
    ) -> list[dict]:
        """
        批改所有答題並更新學習狀態。

        Args:
            task_id: 任務 UUID
            student_id: 學生 UUID
            answers: 答題列表，每項包含：
                question, topic, student_answer, correct_answer
            provider: LLM 供應商

        Returns:
            list[dict]: 批改結果列表，每項包含：
                question, topic, is_correct, student_answer, correct_answer, explanation
        """
        results = []
        wrong_topics: list[str] = []

        for answer in answers:
            result = await self._grade_single(answer, provider)
            results.append(result)

            # 記錄答錯的主題
            if not result["is_correct"]:
                wrong_topics.append(result["topic"])

            # 存入 quiz_records
            await self._save_quiz_record(task_id, student_id, result)

        # 批次更新弱點記憶（Step 6）
        if wrong_topics:
            await self._update_weak_topics(student_id, wrong_topics)

        logger.info(
            "[Grader] 批改完成：%d 題，答對 %d 題",
            len(results),
            sum(1 for r in results if r["is_correct"]),
        )
        return results

    async def _grade_single(self, answer: dict, provider: str | None) -> dict:
        """批改單題答案。"""
        question = answer.get("question", "")
        correct = answer.get("correct_answer", "")
        student = answer.get("student_answer", "")
        topic = answer.get("topic", "未知主題")

        # 簡單文字匹配（先判斷，避免消耗 LLM）
        if student.strip() == correct.strip():
            return {
                "question": question,
                "topic": topic,
                "is_correct": True,
                "student_answer": student,
                "correct_answer": correct,
                "explanation": "答案正確！",
            }

        # 呼叫 LLM 語意批改
        prompt = GRADE_PROMPT.format(
            question=question, correct_answer=correct, student_answer=student
        )
        try:
            raw = await self._llm.complete(
                prompt=prompt,
                temperature=0.1,
                max_tokens=256,
                provider=provider,
            )
            parsed = self._parse_grade(raw)
            return {
                "question": question,
                "topic": topic,
                "is_correct": parsed.get("is_correct", False),
                "student_answer": student,
                "correct_answer": correct,
                "explanation": parsed.get("explanation", "無法取得解析"),
            }
        except Exception as exc:
            logger.error("[Grader] 批改失敗：%s", exc)
            return {
                "question": question,
                "topic": topic,
                "is_correct": False,
                "student_answer": student,
                "correct_answer": correct,
                "explanation": f"批改系統錯誤：{exc}",
            }

    def _parse_grade(self, raw: str) -> dict:
        """解析批改 JSON 回應。"""
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"is_correct": False, "explanation": raw.strip()}

    async def _update_weak_topics(self, student_id: str, wrong_topics: list[str]) -> None:
        """批次遞增答錯主題的弱點計數。"""
        topic_counts: dict[str, int] = {}
        for topic in wrong_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        for topic, count in topic_counts.items():
            await self._state_repo.increment_weak_topic(student_id, topic, count)
        logger.debug("[Grader] 弱點記憶更新：%s", topic_counts)

    async def _save_quiz_record(self, task_id: str, student_id: str, result: dict) -> None:
        """將批改結果存入 quiz_records 資料表。"""
        record_id = str(uuid.uuid4())
        async with aiosqlite.connect(self._settings.database_url) as db:
            await db.execute(
                """
                INSERT INTO quiz_records
                (record_id, task_id, student_id, topic, question,
                 student_answer, correct_answer, is_correct, explanation, answered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id, task_id, student_id,
                    result["topic"], result["question"],
                    result["student_answer"], result["correct_answer"],
                    1 if result["is_correct"] else 0,
                    result.get("explanation", ""),
                    datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()
