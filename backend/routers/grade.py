"""
@module routers.grade
@description 批改路由。從 DB 撈取 Agent 生成的題目與正確答案，
             與學生作答比對後回傳批改結果，並更新弱點記憶。
@dependencies fastapi, tools.grader, core.llm_client, repositories.state_repo
@author 黃柏豪
@version 1.2.0
"""

import json
import logging

import aiosqlite
from fastapi import APIRouter, HTTPException, status

from core.config import get_settings
from models.schemas import APIResponse, GradeRequest, GradeResponse
from tools.grader import Grader
from core.llm_client import get_llm_client
from repositories.state_repo import StateRepository

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post(
    "/grade",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="批改學生測驗答案",
    description=(
        "從 DB 撈取該 task_id 對應的 Agent 生成題目與正確答案，"
        "與學生提交的作答進行比對批改。前端只需傳 quiz_index + student_answer。"
    ),
)
async def grade_answers(request: GradeRequest):
    # 1. 從 DB 撈出該 task 的所有生成題目
    generated_quizzes = await _get_generated_quizzes(request.task_id)
    if not generated_quizzes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到 task_id={request.task_id} 的生成題目，請先執行 POST /api/task 出題。",
        )

    # 2. 建立 quiz_index -> quiz 的映射
    quiz_map = {q["quiz_index"]: q for q in generated_quizzes}

    # 3. 組合學生作答 + 正確答案
    grading_inputs = []
    for answer in request.answers:
        quiz = quiz_map.get(answer.quiz_index)
        if quiz is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"quiz_index={answer.quiz_index} 不存在於該任務的題目中",
            )
        grading_inputs.append({
            "question": quiz["question"],
            "topic": quiz["topic"],
            "correct_answer": quiz["correct_answer"],
            "student_answer": answer.student_answer,
        })

    # 4. 呼叫 Grader 進行批改
    grader = Grader(get_llm_client(), StateRepository())
    try:
        results = await grader.grade_all(
            task_id=request.task_id,
            student_id=request.student_id,
            answers=grading_inputs,
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
                updated_weak_topics=weak_topics,
            ).model_dump(),
        )
    except Exception as exc:
        logger.error("批改失敗：%s", exc)
        return APIResponse(
            status="error",
            error={"code": "GRADE_ERROR", "message": f"批改失敗：{exc}"},
        )


async def _get_generated_quizzes(task_id: str) -> list[dict]:
    """從 DB 撈取指定 task 的所有生成題目。"""
    async with aiosqlite.connect(settings.database_url) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT quiz_index, topic, question, options, correct_answer, explanation
            FROM generated_quizzes
            WHERE task_id = ?
            ORDER BY quiz_index ASC
            """,
            (task_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    quizzes = []
    for row in rows:
        q = dict(row)
        # options 是 JSON 字串，解析回 list
        if isinstance(q.get("options"), str):
            try:
                q["options"] = json.loads(q["options"])
            except (json.JSONDecodeError, TypeError):
                q["options"] = []
        quizzes.append(q)

    return quizzes
