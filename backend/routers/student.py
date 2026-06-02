"""
@module routers.student
@description 學生狀態路由。
@dependencies fastapi, repositories.state_repo
@author 黃柏豪
@version 1.1.0
"""

from fastapi import APIRouter, status, HTTPException
from models.schemas import APIResponse, StudentStateResponse
from repositories.state_repo import StateRepository
from datetime import datetime

router = APIRouter()

@router.get(
    "/student/{student_id}/state",
    response_model=APIResponse,
    summary="取得學生學習狀態",
)
async def get_student_state(student_id: str):
    repo = StateRepository()
    state = await repo.get_or_create(student_id)
    
    return APIResponse(
        status="success",
        data=StudentStateResponse(
            student_id=state["student_id"],
            student_name=state.get("student_name"),
            current_subject=state.get("current_subject"),
            weak_topics=state.get("weak_topics", {}),
            completed_chapters=state.get("completed_chapters", []),
            preferred_quiz_type=state.get("preferred_quiz_type", "multiple_choice"),
            last_updated=datetime.fromisoformat(state["last_updated"])
        ).model_dump()
    )
