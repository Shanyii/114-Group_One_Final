"""
@module routers.student
@description 學生狀態路由。
@dependencies fastapi, repositories.state_repo
@author 黃柏豪
@version 1.1.0
"""

from fastapi import APIRouter, status, HTTPException
from models.schemas import APIResponse, StudentStateResponse, WeakTopicRequest
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

@router.post(
    "/student/weakness",
    response_model=APIResponse,
    summary="新增或遞增學生弱點主題",
    description="當學生點擊詞彙閃卡『還不熟』時，將詞彙名稱作為弱點主題寫入資料庫。",
)
async def add_weak_topic(request: WeakTopicRequest):
    repo = StateRepository()
    state = await repo.increment_weak_topic(request.student_id, request.topic, request.count)
    
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


@router.get(
    "/student/{student_id}/history",
    response_model=APIResponse,
    summary="取得學生學習歷程（包含上傳檔案、答題對錯紀錄）",
)
async def get_student_history(student_id: str):
    from core.config import get_settings
    import aiosqlite
    
    settings = get_settings()
    db_path = settings.database_url
    
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. 查詢上傳講義歷史
        async with db.execute(
            "SELECT document_id, filename, file_type, uploaded_at FROM documents WHERE student_id = ? ORDER BY uploaded_at DESC",
            (student_id,)
        ) as cursor:
            docs = [dict(row) for row in await cursor.fetchall()]

        # 1.1 查詢講義存取日誌
        async with db.execute(
            "SELECT id, document_id, filename, file_type, action, timestamp FROM document_logs WHERE student_id = ? ORDER BY timestamp DESC",
            (student_id,)
        ) as cursor:
            doc_logs = [dict(row) for row in await cursor.fetchall()]
            
        # 2. 查詢答題歷史
        async with db.execute(
            "SELECT record_id, topic, question, student_answer, correct_answer, is_correct, answered_at FROM quiz_records WHERE student_id = ? ORDER BY answered_at DESC",
            (student_id,)
        ) as cursor:
            quizzes = [dict(row) for row in await cursor.fetchall()]
            
    return APIResponse(
        status="success",
        data={
            "documents": docs,
            "document_logs": doc_logs,
            "quiz_records": quizzes
        }
    )


@router.delete(
    "/student/{student_id}/weakness/{topic}",
    response_model=APIResponse,
    summary="刪除學生特定的弱點主題",
)
async def delete_weak_topic(student_id: str, topic: str):
    import uuid
    try:
        uuid.UUID(student_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="student_id 必須為合法的 UUID 格式",
        )
        
    repo = StateRepository()
    state = await repo.delete_weak_topic(student_id, topic)
    
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

