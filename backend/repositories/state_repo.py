"""
@module state_repo
@description 學生學習狀態 Repository。提供 CRUD 操作，使用 aiosqlite 支援非同步存取。
             student_id 由前端產生（ADR Q4），首次 upsert 時自動建立初始 State。
@dependencies aiosqlite, models.db_models, core.config
@author 黃柏豪（後端 / 系統整合）
@version 1.1.0
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import aiosqlite

from core.config import get_settings

logger = logging.getLogger(__name__)

# ── 初始 State 預設值 ─────────────────────────────────────────────────────────
DEFAULT_WEAK_TOPICS: dict = {}
DEFAULT_COMPLETED_CHAPTERS: list = []
DEFAULT_QUIZ_TYPE: str = "multiple_choice"


class StateRepository:
    """
    學生學習狀態 CRUD Repository。

    所有方法皆為 async，使用 aiosqlite 避免阻塞事件迴圈。
    """

    def __init__(self) -> None:
        self.db_path = get_settings().database_url

    async def get(self, student_id: str) -> dict | None:
        """
        查詢學生學習狀態。

        Args:
            student_id: 學生 UUID（前端產生）

        Returns:
            dict: 學習狀態字典；若不存在回傳 None
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return self._row_to_dict(row)

    async def get_or_create(self, student_id: str) -> dict:
        """
        查詢學習狀態，若不存在則自動建立初始 State。

        Args:
            student_id: 學生 UUID

        Returns:
            dict: 學習狀態字典（保證非 None）
        """
        state = await self.get(student_id)
        if state is None:
            logger.info("[StateRepo] 首次建立學生 State：%s", student_id)
            await self._create_initial(student_id)
            state = await self.get(student_id)
        return state  # type: ignore

    async def upsert(self, student_id: str, updates: dict) -> dict:
        """
        更新學習狀態（部分更新）。

        Args:
            student_id: 學生 UUID
            updates: 要更新的欄位字典，支援的鍵：
                     weak_topics, completed_chapters, current_subject,
                     student_name, preferred_quiz_type

        Returns:
            dict: 更新後的完整學習狀態
        """
        # 確保記錄存在
        await self.get_or_create(student_id)

        set_clauses = []
        params = []

        if "weak_topics" in updates:
            set_clauses.append("weak_topics = ?")
            params.append(json.dumps(updates["weak_topics"], ensure_ascii=False))

        if "completed_chapters" in updates:
            set_clauses.append("completed_chapters = ?")
            params.append(json.dumps(updates["completed_chapters"], ensure_ascii=False))

        if "current_subject" in updates:
            set_clauses.append("current_subject = ?")
            params.append(updates["current_subject"])

        if "student_name" in updates:
            set_clauses.append("student_name = ?")
            params.append(updates["student_name"])

        if "preferred_quiz_type" in updates:
            set_clauses.append("preferred_quiz_type = ?")
            params.append(updates["preferred_quiz_type"])

        set_clauses.append("last_updated = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(student_id)

        if len(set_clauses) > 1:  # 至少有一個欄位更新
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    f"UPDATE students SET {', '.join(set_clauses)} WHERE student_id = ?",
                    params,
                )
                await db.commit()
            logger.debug("[StateRepo] 已更新學生狀態：%s", student_id)

        return await self.get(student_id)  # type: ignore

    async def increment_weak_topic(self, student_id: str, topic: str, count: int = 1) -> dict:
        """
        遞增指定弱點主題的錯誤計數（答錯 +1）。

        Args:
            student_id: 學生 UUID
            topic: 弱點主題名稱，如 'TF-IDF'
            count: 遞增數量（預設 1）

        Returns:
            dict: 更新後的完整學習狀態
        """
        state = await self.get_or_create(student_id)
        weak_topics: dict = state.get("weak_topics", {})
        weak_topics[topic] = weak_topics.get(topic, 0) + count
        return await self.upsert(student_id, {"weak_topics": weak_topics})

    async def add_completed_chapter(self, student_id: str, chapter: str) -> dict:
        """
        新增已完成章節（若尚未記錄）。

        Args:
            student_id: 學生 UUID
            chapter: 章節名稱，如 'Chapter 3'

        Returns:
            dict: 更新後的完整學習狀態
        """
        state = await self.get_or_create(student_id)
        chapters: list = state.get("completed_chapters", [])
        if chapter not in chapters:
            chapters.append(chapter)
            return await self.upsert(student_id, {"completed_chapters": chapters})
        return state

    # ── 內部輔助方法 ──────────────────────────────────────────────────────────

    async def _create_initial(self, student_id: str) -> None:
        """建立初始學習狀態記錄。"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO students
                (student_id, weak_topics, completed_chapters, preferred_quiz_type, last_updated)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    json.dumps(DEFAULT_WEAK_TOPICS),
                    json.dumps(DEFAULT_COMPLETED_CHAPTERS),
                    DEFAULT_QUIZ_TYPE,
                    datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict:
        """將 DB Row 轉換為 Python dict，並解析 JSON 欄位。"""
        d = dict(row)
        d["weak_topics"] = json.loads(d.get("weak_topics") or "{}")
        d["completed_chapters"] = json.loads(d.get("completed_chapters") or "[]")
        return d
