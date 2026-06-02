"""
@module log_repo
@description 雙層 Log Repository（ADR-005）。
             - DevLog：技術詳情（工具呼叫鏈、duration_ms），保留 30 天
             - WorkflowLog：使用者可讀步驟摘要，永久保留，支援 SSE 推播
@dependencies aiosqlite, core.config
@author 黃柏豪（後端 / 系統整合）
@version 1.1.0
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator

import aiosqlite

from core.config import get_settings

logger = logging.getLogger(__name__)

# ── SSE 訂閱者管理（task_id -> asyncio.Queue）────────────────────────────────
_sse_subscribers: dict[str, list[asyncio.Queue]] = {}


class LogRepository:
    """
    雙層 Log Repository。

    - save_dev_log(): 儲存技術詳情至 dev_logs
    - append_workflow_step(): 新增步驟至 workflow_logs 並 SSE 推播
    - stream_workflow(): 訂閱指定任務的 SSE 事件流
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db_path = self.settings.database_url

    # ── Developer Log ─────────────────────────────────────────────────────────

    async def save_dev_log(
        self,
        task_id: str,
        user_input: str,
        intent: str,
        tools_called: list[dict],
        retrieved_topic: str | None,
        final_result: str | None,
        total_duration_ms: int,
    ) -> str:
        """
        儲存完整技術 Log 至 dev_logs 資料表。

        Args:
            task_id: 任務 UUID
            user_input: 使用者原始輸入
            intent: 判斷的意圖類型
            tools_called: 工具呼叫記錄列表
            retrieved_topic: 主要查詢主題
            final_result: 最終結果描述
            total_duration_ms: 總執行時間（毫秒）

        Returns:
            str: 生成的 log_id（UUID）
        """
        log_id = str(uuid.uuid4())
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO dev_logs
                    (log_id, task_id, user_input, intent, tools_called,
                     retrieved_topic, final_result, total_duration_ms, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        log_id, task_id, user_input, intent,
                        json.dumps(tools_called, ensure_ascii=False),
                        retrieved_topic, final_result, total_duration_ms,
                        datetime.utcnow().isoformat(),
                    ),
                )
                await db.commit()
            logger.debug("[LogRepo] DevLog 已儲存：task_id=%s, log_id=%s", task_id, log_id)
        except Exception as exc:
            logger.error("[LogRepo] DevLog 儲存失敗：%s", exc)
            raise
        return log_id

    async def get_dev_log(self, task_id: str) -> dict | None:
        """
        查詢指定任務的 Developer Log。

        Args:
            task_id: 任務 UUID

        Returns:
            dict: Dev Log 字典；若不存在回傳 None
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM dev_logs WHERE task_id = ?", (task_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                d = dict(row)
                d["tools_called"] = json.loads(d.get("tools_called") or "[]")
                return d

    async def cleanup_old_dev_logs(self) -> int:
        """
        清理超過保留期限的 Developer Log（保留天數由 settings 控制）。

        Returns:
            int: 已刪除的 Log 筆數
        """
        cutoff = datetime.utcnow() - timedelta(days=self.settings.dev_log_retention_days)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM dev_logs WHERE timestamp < ?", (cutoff.isoformat(),)
            )
            await db.commit()
            deleted = cursor.rowcount
        if deleted > 0:
            logger.info("[LogRepo] 清理過期 DevLog %d 筆（保留 %d 天）", deleted, self.settings.dev_log_retention_days)
        return deleted

    # ── Workflow Log（使用者可讀 + SSE）──────────────────────────────────────

    async def append_workflow_step(
        self,
        task_id: str,
        step_index: int,
        step_name: str,
        step_display: str,
        status: str = "success",
    ) -> None:
        """
        新增一筆 Workflow Log 步驟，並推播至 SSE 訂閱者。

        Args:
            task_id: 任務 UUID
            step_index: 步驟序號（1–8）
            step_name: 步驟函式名稱，如 'retrieve_content'
            step_display: 使用者可讀描述，如 '[Step 2] 查詢相關段落完成'
            status: 'running' | 'success' | 'failed'
        """
        now = datetime.utcnow()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO workflow_logs
                    (task_id, step_index, step_name, step_display, status, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (task_id, step_index, step_name, step_display, status, now.isoformat()),
                )
                await db.commit()
        except Exception as exc:
            logger.error("[LogRepo] WorkflowLog 儲存失敗：%s", exc)

        # SSE 推播
        event_data = {
            "task_id": task_id,
            "step_index": step_index,
            "step_name": step_name,
            "step_display": step_display,
            "status": status,
            "timestamp": now.isoformat(),
        }
        await self._broadcast_sse(task_id, event_data)

    async def get_workflow_steps(self, task_id: str) -> list[dict]:
        """
        查詢指定任務的所有 Workflow Log 步驟（依序排列）。

        Args:
            task_id: 任務 UUID

        Returns:
            list[dict]: 步驟列表
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM workflow_logs
                WHERE task_id = ?
                ORDER BY step_index ASC
                """,
                (task_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def stream_workflow(
        self, task_id: str, poll_interval: float = 0.5
    ) -> AsyncGenerator[str, None]:
        """
        SSE 事件流生成器（ADR-002：單向推播）。

        FastAPI 的 StreamingResponse 或 EventSourceResponse 使用此生成器。
        當任務完成或失敗後自動結束流。

        Args:
            task_id: 任務 UUID
            poll_interval: 輪詢間隔秒數

        Yields:
            str: SSE 格式字串，如 'data: {...}\\n\\n'
        """
        queue: asyncio.Queue = asyncio.Queue()

        # 訂閱此任務的 SSE 推播
        if task_id not in _sse_subscribers:
            _sse_subscribers[task_id] = []
        _sse_subscribers[task_id].append(queue)

        try:
            # 先推播已有的歷史步驟（補齊已錯過的事件）
            existing_steps = await self.get_workflow_steps(task_id)
            for step in existing_steps:
                yield f"data: {json.dumps(step, ensure_ascii=False)}\n\n"

            # 等待新事件
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=poll_interval * 20)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                    # 若任務已完成，結束 SSE 流
                    if event.get("status") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    # 心跳保持連線
                    yield ": heartbeat\n\n"
        finally:
            # 取消訂閱
            if task_id in _sse_subscribers:
                _sse_subscribers[task_id] = [
                    q for q in _sse_subscribers[task_id] if q is not queue
                ]
                if not _sse_subscribers[task_id]:
                    del _sse_subscribers[task_id]

    # ── 內部 SSE 廣播 ─────────────────────────────────────────────────────────

    async def _broadcast_sse(self, task_id: str, event: dict) -> None:
        """廣播 SSE 事件至所有訂閱者。"""
        if task_id not in _sse_subscribers:
            return
        for queue in _sse_subscribers[task_id]:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("[LogRepo] SSE Queue 已滿，丟棄事件：%s", task_id)
