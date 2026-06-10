"""
@module db_models
@description SQLAlchemy 資料表定義。對應 architecture.md ER 圖中的五張資料表，
             並依 ADR-005 將 Log 拆分為 dev_logs（技術詳情）與 workflow_logs（使用者摘要）。
@dependencies sqlalchemy, aiosqlite
@author 黃柏豪（後端 / 系統整合）
@version 1.1.0
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    Index,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship
import aiosqlite


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基礎類別。"""
    pass


# ── 學生資料表 ────────────────────────────────────────────────────────────────

class Student(Base):
    """
    學生學習狀態資料表。

    儲存每位學生的弱點記憶、章節完成進度，
    `student_id` 由前端 crypto.randomUUID() 生成（ADR Q4）。
    """
    __tablename__ = "students"

    student_id = Column(String(36), primary_key=True, comment="UUID，由前端生成")
    username = Column(String(50), unique=True, nullable=True, comment="帳號")
    password_hash = Column(String(100), nullable=True, comment="雜湊密碼")
    student_name = Column(String(100), nullable=True, comment="學生姓名（選填）")
    current_subject = Column(String(200), nullable=True, comment="目前科目")
    # JSON 欄位：{ "TF-IDF": 2, "PCFG 機率計算": 3 }
    weak_topics = Column(JSON, nullable=False, default=dict, comment="弱點主題與錯誤次數")
    # JSON 欄位：["Chapter 1", "Chapter 2"]
    completed_chapters = Column(JSON, nullable=False, default=list, comment="已完成章節")
    preferred_quiz_type = Column(
        String(50), nullable=False, default="multiple_choice",
        comment="偏好題型：multiple_choice | true_false | definition"
    )
    last_updated = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 關聯
    tasks = relationship("Task", back_populates="student", lazy="dynamic")
    documents = relationship("Document", back_populates="student", lazy="dynamic")
    quiz_records = relationship("QuizRecord", back_populates="student", lazy="dynamic")


# ── 文件資料表 ────────────────────────────────────────────────────────────────

class Document(Base):
    """
    使用者上傳的講義文件資料表。

    raw_text 僅在 Session 有效期間使用，原始檔案上傳後即解析並刪除（安全性考量）。
    """
    __tablename__ = "documents"

    document_id = Column(String(36), primary_key=True, comment="UUID")
    student_id = Column(String(36), ForeignKey("students.student_id"), nullable=False)
    filename = Column(String(255), nullable=False, comment="原始檔案名稱")
    file_type = Column(String(10), nullable=False, comment="pdf | pptx")
    # 解析後的純文字，儲存於 DB 以供 RAG 建索引（不保留原始二進位檔）
    raw_text = Column(Text, nullable=True, comment="解析後純文字（建索引後可清除）")
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 關聯
    student = relationship("Student", back_populates="documents")
    tasks = relationship("Task", back_populates="document", lazy="dynamic")

    __table_args__ = (
        Index("idx_documents_student_id", "student_id"),
    )


# ── 任務資料表 ────────────────────────────────────────────────────────────────

class Task(Base):
    """
    任務資料表。記錄每次使用者發起的 Agent 任務執行狀態。

    使用 FastAPI BackgroundTasks 非同步執行（ADR-004），
    前端透過 GET /api/task/{task_id} 或 SSE 追蹤狀態。
    """
    __tablename__ = "tasks"

    task_id = Column(String(36), primary_key=True, comment="UUID")
    student_id = Column(String(36), ForeignKey("students.student_id"), nullable=False)
    document_id = Column(String(36), ForeignKey("documents.document_id"), nullable=True)
    intent = Column(String(50), nullable=True, comment="summary | quiz | plan | full")
    status = Column(
        String(20), nullable=False, default="pending",
        comment="pending | running | completed | failed"
    )
    user_instruction = Column(Text, nullable=True, comment="使用者原始指令")
    result_summary = Column(Text, nullable=True, comment="任務最終結果摘要")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # 關聯
    student = relationship("Student", back_populates="tasks")
    document = relationship("Document", back_populates="tasks")
    dev_log = relationship("DevLog", back_populates="task", uselist=False)
    workflow_logs = relationship("WorkflowLog", back_populates="task", lazy="dynamic")
    quiz_records = relationship("QuizRecord", back_populates="task", lazy="dynamic")

    __table_args__ = (
        Index("idx_tasks_student_id", "student_id"),
        Index("idx_tasks_status", "status"),
    )


# ── Developer Log 資料表（ADR-005：雙層 Log）─────────────────────────────────

class DevLog(Base):
    """
    Developer Log 資料表（技術詳情，供開發者除錯）。

    記錄完整工具呼叫鏈、duration_ms、LLM prompt 等技術細節。
    保留 30 天後自動清除（dev_log_retention_days）。
    """
    __tablename__ = "dev_logs"

    log_id = Column(String(36), primary_key=True, comment="UUID")
    task_id = Column(String(36), ForeignKey("tasks.task_id"), nullable=False, unique=True)
    user_input = Column(Text, nullable=True, comment="使用者原始輸入")
    intent = Column(String(50), nullable=True)
    # JSON 陣列：[{ tool, input, output_summary, status, duration_ms }]
    tools_called = Column(JSON, nullable=False, default=list, comment="完整工具呼叫鏈")
    retrieved_topic = Column(String(200), nullable=True, comment="主要查詢主題")
    final_result = Column(Text, nullable=True, comment="最終結果描述")
    total_duration_ms = Column(Integer, nullable=True, comment="總執行時間（毫秒）")
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 關聯
    task = relationship("Task", back_populates="dev_log")

    __table_args__ = (
        Index("idx_dev_logs_timestamp", "timestamp"),
    )


# ── Workflow Log 資料表（ADR-005：雙層 Log）──────────────────────────────────

class WorkflowLog(Base):
    """
    Workflow Log 資料表（使用者可讀步驟摘要，供前端 Agent Terminal 顯示）。

    每筆記錄代表任務中一個步驟的狀態，透過 SSE 即時推送至前端。
    永久保留（與學習紀錄等同重要性）。
    """
    __tablename__ = "workflow_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), ForeignKey("tasks.task_id"), nullable=False)
    step_index = Column(Integer, nullable=False, comment="步驟序號（1–8）")
    step_name = Column(String(100), nullable=False, comment="步驟名稱，如 retrieve_content")
    step_display = Column(Text, nullable=False, comment="使用者可讀描述，如 [Step 2] 查詢相關段落完成")
    status = Column(String(20), nullable=False, comment="running | success | failed")
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 關聯
    task = relationship("Task", back_populates="workflow_logs")

    __table_args__ = (
        Index("idx_workflow_logs_task_id", "task_id"),
    )


# ── 測驗作答紀錄資料表 ────────────────────────────────────────────────────────

class QuizRecord(Base):
    """
    測驗作答紀錄資料表。

    批改結果永久保留，用於弱點分析與個人化複習建議。
    """
    __tablename__ = "quiz_records"

    record_id = Column(String(36), primary_key=True, comment="UUID")
    task_id = Column(String(36), ForeignKey("tasks.task_id"), nullable=False)
    student_id = Column(String(36), ForeignKey("students.student_id"), nullable=False)
    topic = Column(String(200), nullable=False, comment="對應主題，如 TF-IDF")
    question = Column(Text, nullable=False, comment="題目內容")
    options = Column(JSON, nullable=True, comment="選項列表（選擇題用）")
    student_answer = Column(Text, nullable=False, comment="學生作答")
    correct_answer = Column(Text, nullable=False, comment="正確答案")
    is_correct = Column(Boolean, nullable=False)
    explanation = Column(Text, nullable=True, comment="解析說明")
    answered_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 關聯
    task = relationship("Task", back_populates="quiz_records")
    student = relationship("Student", back_populates="quiz_records")

    __table_args__ = (
        Index("idx_quiz_records_student_id", "student_id"),
        Index("idx_quiz_records_topic", "topic"),
    )


# ── Agent 生成題目資料表 ──────────────────────────────────────────────────────

class GeneratedQuiz(Base):
    """
    Agent 生成的測驗題目資料表。

    當 Agent 執行 generate_quiz 步驟後，自動把題目與正確答案存入此表。
    批改時直接從這裡撈取正確答案，前端不需要傳 correct_answer。
    """
    __tablename__ = "generated_quizzes"

    quiz_id = Column(String(36), primary_key=True, comment="UUID")
    task_id = Column(String(36), ForeignKey("tasks.task_id"), nullable=False)
    quiz_index = Column(Integer, nullable=False, comment="題目序號（從 0 開始）")
    topic = Column(String(200), nullable=False, comment="對應主題")
    question = Column(Text, nullable=False, comment="題目內容")
    options = Column(JSON, nullable=True, comment="選項列表")
    correct_answer = Column(Text, nullable=False, comment="正確答案")
    explanation = Column(Text, nullable=True, comment="解析說明")
    question_type = Column(String(50), nullable=False, default="multiple_choice")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_generated_quizzes_task_id", "task_id"),
    )


# ── 資料庫初始化工具函式 ──────────────────────────────────────────────────────

def create_tables(database_url: str) -> None:
    """
    同步建立所有資料表（供啟動時呼叫），若欄位不存在則進行動態升級。

    Args:
        database_url: SQLite 資料庫路徑，如 './learning.db'
    """
    engine = create_engine(f"sqlite:///{database_url}", echo=False)
    Base.metadata.create_all(engine)
    
    # 動態檢查並升級欄位
    from sqlalchemy import inspect
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("students")]
    
    with engine.begin() as conn:
        if "username" not in columns:
            conn.execute(text("ALTER TABLE students ADD COLUMN username VARCHAR(50)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_students_username ON students (username)"))
        if "password_hash" not in columns:
            conn.execute(text("ALTER TABLE students ADD COLUMN password_hash VARCHAR(100)"))
            
    engine.dispose()
