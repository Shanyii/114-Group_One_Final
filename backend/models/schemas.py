"""
@module schemas
@description Pydantic v2 請求 / 回應 Schema 定義。
             所有 API 端點使用此模組進行資料驗證與序列化，
             確保型別安全並自動生成 OpenAPI 文件。
@dependencies pydantic
@author 黃柏豪（後端 / 系統整合）
@version 1.1.0
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator
import uuid


# ── 通用回應包裝器 ────────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    """所有 API 端點的統一回應格式。"""
    status: Literal["success", "error"] = "success"
    data: Any = None
    error: Optional[ErrorDetail] = None


class ErrorDetail(BaseModel):
    """API 錯誤詳情。"""
    code: str = Field(..., description="錯誤代碼，如 FILE_TOO_LARGE")
    message: str = Field(..., description="中文錯誤說明")


# ── 上傳相關 Schema ───────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """POST /api/upload 回應。"""
    document_id: str = Field(..., description="UUID，供後續任務引用")
    filename: str
    file_type: str


# ── 任務相關 Schema ───────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    """POST /api/task 請求體。"""
    student_id: str = Field(
        ..., description="前端 crypto.randomUUID() 生成的 UUID（ADR Q4）"
    )
    document_id: str = Field(..., description="上傳時取得的 document_id")
    instruction: str = Field(
        ..., min_length=1, max_length=1000,
        description="使用者自然語言指令，如「幫我整理重點並出 3 題選擇題」"
    )
    llm_provider: Optional[Literal["gemini", "openai"]] = Field(
        None, description="指定 LLM 供應商（不填則用設定預設值）"
    )

    @field_validator("student_id", "document_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        """驗證 UUID 格式。"""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("必須為合法的 UUID 格式")
        return v


class TaskCreateResponse(BaseModel):
    """POST /api/task 回應（立即回傳 task_id，任務背景執行）。"""
    task_id: str
    status: Literal["pending"] = "pending"


class TaskStatusResponse(BaseModel):
    """GET /api/task/{task_id} 回應。"""
    task_id: str
    status: Literal["pending", "running", "completed", "failed"]
    intent: Optional[str] = None
    steps_done: int = 0
    result_summary: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# ── 學習狀態相關 Schema ───────────────────────────────────────────────────────

class WeakTopicRequest(BaseModel):
    """POST /api/student/weakness 請求體。"""
    student_id: str = Field(..., description="學生 UUID")
    topic: str = Field(..., description="弱點主題/核心詞彙名稱")
    count: int = Field(default=1, description="遞增數量（預設 1）")

    @field_validator("student_id")
    @classmethod
    def validate_student_id(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("student_id 必須為合法的 UUID 格式")
        return v


class StudentStateResponse(BaseModel):
    """GET /api/student/{student_id}/state 回應。"""
    student_id: str
    student_name: Optional[str] = None
    current_subject: Optional[str] = None
    weak_topics: dict[str, int] = Field(
        default_factory=dict,
        description="弱點主題與錯誤次數，如 {'TF-IDF': 2}"
    )
    completed_chapters: list[str] = Field(default_factory=list)
    preferred_quiz_type: str = "multiple_choice"
    last_updated: datetime


# ── 批改相關 Schema ───────────────────────────────────────────────────────────

class AnswerItem(BaseModel):
    """單題作答（簡化版：前端只需傳題目序號和學生答案）。"""
    quiz_index: int = Field(..., description="題目序號（對應 generated_quizzes 的 quiz_index）")
    student_answer: str = Field(..., description="學生作答")


class GradeRequest(BaseModel):
    """POST /api/grade 請求體。"""
    task_id: str
    student_id: str
    answers: list[AnswerItem] = Field(..., min_length=1, max_length=20)

    @field_validator("task_id", "student_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("必須為合法的 UUID 格式")
        return v


class GradeResultItem(BaseModel):
    """單題批改結果。"""
    question: str
    topic: str
    is_correct: bool
    student_answer: str
    correct_answer: str
    explanation: str


class GradeResponse(BaseModel):
    """POST /api/grade 回應。"""
    task_id: str
    total: int
    correct_count: int
    accuracy: float = Field(..., description="答對率 0.0–1.0")
    grading_results: list[GradeResultItem]
    updated_weak_topics: dict[str, int] = Field(
        description="批改後更新的弱點計數"
    )
    study_plan_hint: Optional[str] = Field(
        None, description="簡短複習建議（基於本次弱點）"
    )


# ── Log 相關 Schema ───────────────────────────────────────────────────────────

class ToolCallRecord(BaseModel):
    """單次工具呼叫紀錄（Dev Log 中的元素）。"""
    tool: str = Field(..., description="工具函式名稱，如 retrieve_content")
    input_summary: str = Field(..., description="輸入摘要")
    output_summary: str = Field(..., description="輸出摘要")
    status: Literal["success", "failed"] = "success"
    duration_ms: int = Field(..., description="執行時間（毫秒）")


class DevLogResponse(BaseModel):
    """GET /api/log/{task_id} 回應（Developer Log）。"""
    log_id: str
    task_id: str
    user_input: Optional[str] = None
    intent: Optional[str] = None
    tools_called: list[ToolCallRecord] = Field(default_factory=list)
    retrieved_topic: Optional[str] = None
    final_result: Optional[str] = None
    total_duration_ms: Optional[int] = None
    timestamp: datetime


class WorkflowStepEvent(BaseModel):
    """SSE 推播的 Workflow Log 步驟事件（使用者可讀）。"""
    task_id: str
    step_index: int
    step_name: str
    step_display: str = Field(..., description="如 [Step 2] 查詢相關段落完成")
    status: Literal["running", "success", "failed"]
    timestamp: datetime


# ── 內部工具函式回傳型別 ──────────────────────────────────────────────────────

class QuizQuestion(BaseModel):
    """AI 生成的測驗題目。"""
    topic: str
    question: str
    options: Optional[list[str]] = None  # 選擇題才有
    correct_answer: str
    explanation: str
    question_type: Literal["multiple_choice", "true_false", "definition"] = "multiple_choice"


class GlossaryItem(BaseModel):
    """核心詞彙閃卡項目。"""
    term: str = Field(..., description="名詞名稱")
    definition: str = Field(..., alias="def", description="定義")

class SummaryResult(BaseModel):
    """重點摘要結果。"""
    topic: str
    summary: str
    key_points: list[str] = Field(default_factory=list, description="條列式重點")
    glossary: list[GlossaryItem] = Field(default_factory=list, description="核心詞彙閃卡清單")


class StudyPlan(BaseModel):
    """個人化複習計畫。"""
    student_id: str
    exam_date: Optional[str] = None
    weak_topics: dict[str, int]
    recommendations: list[StudyRecommendation] = Field(default_factory=list)
    estimated_study_hours: float = 0.0


class StudyRecommendation(BaseModel):
    """單項複習建議。"""
    topic: str
    priority: Literal["high", "medium", "low"]
    reason: str
    suggested_actions: list[str]


# ── 聊天相關 Schema ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """POST /api/chat 請求體。"""
    student_id: str = Field(
        ..., description="學生 UUID"
    )
    document_id: Optional[str] = Field(
        None, description="上傳時取得的 document_id，非強制，允許訪客預設模式為 None"
    )
    message: str = Field(
        ..., min_length=1, max_length=2000,
        description="學生的問題內容"
    )
    llm_provider: Optional[Literal["gemini", "openai", "mock"]] = Field(
        None, description="指定 LLM 供應商（不填則用設定預設值）"
    )

    @field_validator("student_id")
    @classmethod
    def validate_student_id(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("student_id 必須為合法的 UUID 格式")
        return v

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("document_id 必須為合法的 UUID 格式")
        return v


class ChatResponse(BaseModel):
    """POST /api/chat 回應。"""
    answer: str = Field(..., description="AI 生成的回答")
    retrieved_passages: list[dict] = Field(
        default_factory=list,
        description="檢索出的講義參考段落列表"
    )


# 解決前向引用
StudyPlan.model_rebuild()
APIResponse.model_rebuild()
ChatResponse.model_rebuild()

