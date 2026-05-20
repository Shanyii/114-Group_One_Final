"""
@module routers.grade
@description 批改路由。接收學生的測驗作答，呼叫 Grader 進行批改並回傳結果。
@dependencies fastapi, tools.grader, core.llm_client, repositories.state_repo
@author 黃柏豪
@version 1.1.0
"""

import logging

from fastapi import APIRouter, status

from models.schemas import APIResponse, GradeRequest, GradeResponse
from tools.grader import Grader
from core.llm_client import get_llm_client
from repositories.state_repo import StateRepository

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/grade",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="批改學生測驗答案",
)
async def grade_answers(request: GradeRequest):
    grader = Grader(get_llm_client(), StateRepository())
    
    try:
        results = await grader.grade_all(
            task_id=request.task_id,
            student_id=request.student_id,
            answers=[a.model_dump() for a in request.answers]
        )
        
        correct_count = sum(1 for r in results if r["is_correct"])
        total = len(results)
        
        # 取得更新後的弱點
        state_repo = StateRepository()
        state = await state_repo.get(request.student_id)
        weak_topics = state.get("weak_topics", {}) if state else {}
        
        return APIResponse(
            status="success",
            data=GradeResponse(
                task_id=request.task_id,
                total=total,
                correct_count=correct_count,
                accuracy=correct_count / total if total > 0 else 0,
                grading_results=results,
                updated_weak_topics=weak_topics
            ).model_dump()
        )
    except Exception as exc:
        logger.error("批改失敗：%s", exc)
        return APIResponse(
            status="error",
            error={"code": "GRADE_ERROR", "message": f"批改失敗：{exc}"}
        )
