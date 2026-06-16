"""
@module config
@description 系統設定模組，從 .env 載入所有環境變數並提供型別安全的存取介面。
@dependencies pydantic-settings, python-dotenv
@author 黃柏豪（後端 / 系統整合）
@version 1.2.0
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from functools import lru_cache


def _find_env_file() -> str:
    """自動偵測 .env 位置，支援從根目錄或 backend 目錄啟動。"""
    # 優先：與 config.py 同層的上一層（backend/.env）
    this_dir = Path(__file__).resolve().parent.parent  # backend/
    candidate = this_dir / ".env"
    if candidate.exists():
        return str(candidate)
    # 其次：CWD 下的 .env
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return str(cwd_env)
    # 最後：CWD 下的 backend/.env
    cwd_backend_env = Path.cwd() / "backend" / ".env"
    if cwd_backend_env.exists():
        return str(cwd_backend_env)
    return ".env"  # fallback


class Settings(BaseSettings):
    """系統全域設定，對應 .env.example 中所有鍵值。"""

    # ── 系統金鑰設定 ──────────────────────────────────────────────────────
    secret_key: str = Field("studyagent_secure_secret_key_2026", description="JWT/Session 簽章私鑰")

    # ── LLM 設定（ADR Q1：Gemini 開發 / GPT-4o Demo）────────────────────
    gemini_api_key: str = Field(..., description="Google Gemini API 金鑰")
    openai_api_key: str = Field("", description="OpenAI API 金鑰（Demo 用）")
    llm_provider: str = Field("gemini", description="LLM 供應商：gemini | openai")
    gemini_model: str = Field("gemini-2.0-flash", description="Gemini 模型名稱")
    openai_model: str = Field("gpt-4o", description="OpenAI 模型名稱（Demo）")
    embedding_model: str = Field(
        "models/text-embedding-004", description="Embedding 模型（Google）"
    )

    # ── 資料儲存（ADR Q2：ChromaDB 持久化）───────────────────────────────
    chroma_db_dir: str = Field("./chroma_db", description="ChromaDB 本地持久化目錄")
    upload_dir: str = Field("./uploads", description="上傳檔案暫存目錄")
    database_url: str = Field("./learning.db", description="SQLite 資料庫路徑")

    # ── 伺服器（ADR Q3：前後端同機）──────────────────────────────────────
    host: str = Field("0.0.0.0", description="監聽 Host")
    port: int = Field(8000, description="監聽 Port")

    # ── Log 管理 ──────────────────────────────────────────────────────────
    dev_log_retention_days: int = Field(30, description="Developer Log 保留天數")

    # ── 速率限制 ──────────────────────────────────────────────────────────
    rate_limit_per_minute: int = Field(10, description="每分鐘最多呼叫 /api/task 次數")

    # ── RAG 設定 ──────────────────────────────────────────────────────────
    rag_top_k: int = Field(5, description="RAG 查詢返回的最大段落數")
    chunk_size: int = Field(500, description="文件切分的最大字元數（每個 Chunk）")
    chunk_overlap: int = Field(50, description="Chunk 間重疊字元數")

    # ── LLM 重試設定（ADR-001：指數退避）────────────────────────────────
    llm_max_retries: int = Field(3, description="LLM API 呼叫最大重試次數")
    llm_retry_wait_min: float = Field(1.0, description="重試最小等待秒數")
    llm_retry_wait_max: float = Field(10.0, description="重試最大等待秒數")

    @model_validator(mode="after")
    def resolve_paths(self) -> 'Settings':
        """確保所有相對路徑（SQLite、ChromaDB、Uploads）都解析為相對於 backend/ 目錄的絕對路徑，防範 CWD 變更造成的資料丟失。"""
        backend_dir = Path(__file__).resolve().parent.parent
        
        if self.database_url and not os.path.isabs(self.database_url):
            self.database_url = str((backend_dir / self.database_url).resolve())
            
        if self.chroma_db_dir and not os.path.isabs(self.chroma_db_dir):
            self.chroma_db_dir = str((backend_dir / self.chroma_db_dir).resolve())
            
        if self.upload_dir and not os.path.isabs(self.upload_dir):
            self.upload_dir = str((backend_dir / self.upload_dir).resolve())
            
        return self

    model_config = {"env_file": _find_env_file(), "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    取得全域設定單例（使用 lru_cache 確保只初始化一次）。

    Returns:
        Settings: 系統設定物件

    Example:
        >>> settings = get_settings()
        >>> print(settings.llm_provider)
        'gemini'
    """
    return Settings()
