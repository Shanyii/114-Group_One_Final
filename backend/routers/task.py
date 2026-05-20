"""
@module routers.task
@description 任務路由。觸發 Agent 任務（BackgroundTasks 非同步執行）並查詢任務狀態。
@dependencies fastapi, services.orchestrator, core.config
@author 黃柏豪（後端 / 系統整合）
@version 1.1.0
"""

import logging
import uuid
from datetime import datetime

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from core.config import get_settings
from models.schemas import APIResponse, TaskCreateResponse, TaskRequest, TaskStatusResponse
from services.orchestrator import Orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post(
    "/task",
    response_model=APIResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="送出 Agent 任務",
    description="接收使用者指令，立即回傳 task_id（HTTP 202），任務在背景非同步執行（ADR-004）。",
)
async def create_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks,
):
    """
    建立並啟動 Agent 任務（非阻塞）。

    Args:
        request: 包含 student_id, document_id, instruction
        background_tasks: FastAPI BackgroundTasks

    Returns:
        APIResponse: 包含 task_id 與 status='pending'
    """
    task_id = str(uuid.uuid4())

    # 預先寫入 tasks 資料表（狀態 pending）
    try:
        async with aiosqlite.connect(settings.database_url) as db:
            await db.execute(
                """
                INSERT INTO tasks
                (task_id, student_id, document_id, status, user_instruction, created_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (
                    task_id, request.student_id, request.document_id,
                    request.instruction, datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()
    except Exception as exc:
        logger.error("[Router/task] DB 寫入失敗：%s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任務建立失敗，請稍後重試",
        )

    # 非同步背景執行（ADR-004：FastAPI BackgroundTasks）
    orchestrator = Orchestrator()
    background_tasks.add_task(
        orchestrator.execute_task,
        task_id=task_id,
        student_id=request.student_id,
        document_id=request.document_id,
        instruction=request.instruction,
        llm_provider=request.llm_provider,
    )

    logger.info("[Router/task] 任務已建立（背景執行）：task_id=%s", task_id)
    return APIResponse(
        status="success",
        data=TaskCreateResponse(task_id=task_id).model_dump(),
    )


@router.get(
    "/task/{task_id}",
    response_model=APIResponse,
    summary="查詢任務狀態",
    description="取得任務執行狀態（pending | running | completed | failed）與結果摘要。",
)
async def get_task_status(task_id: str):
    """
    查詢任務執行狀態。

    Args:
        task_id: 任務 UUID

    Returns:
        APIResponse: 任務狀態資訊

    Raises:
        404: 任務不存在
    """
    # 驗證 UUID 格式
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="task_id 必須為合法的 UUID 格式",
        )

    async with aiosqlite.connect(settings.database_url) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到任務：{task_id}",
        )

    # 查詢已完成步驟數（從 workflow_logs 計算）
    async with aiosqlite.connect(settings.database_url) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM workflow_logs WHERE task_id = ? AND status = 'success'",
            (task_id,),
        ) as cursor:
            steps_done = (await cursor.fetchone())[0]

    task = dict(row)
    return APIResponse(
        status="success",
        data=TaskStatusResponse(
            task_id=task["task_id"],
            status=task["status"],
            intent=task.get("intent"),
            steps_done=steps_done,
            result_summary=task.get("result_summary"),
            created_at=datetime.fromisoformat(task["created_at"]),
            completed_at=datetime.fromisoformat(task["completed_at"]) if task.get("completed_at") else None,
        ).model_dump(),
    )
