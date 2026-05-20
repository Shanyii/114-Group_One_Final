"""
@module routers.log
@description Log 路由，包含 SSE 推播。
@dependencies fastapi, repositories.log_repo
@author 黃柏豪
@version 1.1.0
"""

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
from repositories.log_repo import LogRepository
from models.schemas import APIResponse, DevLogResponse
from datetime import datetime

router = APIRouter()
log_repo = LogRepository()

@router.get(
    "/log/{task_id}/stream",
    summary="訂閱任務 Workflow Log (SSE)",
)
async def stream_task_log(task_id: str):
    return StreamingResponse(
        log_repo.stream_workflow(task_id),
        media_type="text/event-stream"
    )

@router.get(
    "/log/{task_id}/dev",
    response_model=APIResponse,
    summary="取得 Developer Log",
)
async def get_dev_log(task_id: str):
    dev_log = await log_repo.get_dev_log(task_id)
    if not dev_log:
        return APIResponse(status="error", error={"code": "NOT_FOUND", "message": "找不到 Dev Log"})
        
    return APIResponse(
        status="success",
        data=DevLogResponse(
            log_id=dev_log["log_id"],
            task_id=dev_log["task_id"],
            user_input=dev_log.get("user_input"),
            intent=dev_log.get("intent"),
            tools_called=dev_log.get("tools_called", []),
            retrieved_topic=dev_log.get("retrieved_topic"),
            final_result=dev_log.get("final_result"),
            total_duration_ms=dev_log.get("total_duration_ms"),
            timestamp=datetime.fromisoformat(dev_log["timestamp"])
        ).model_dump()
    )
