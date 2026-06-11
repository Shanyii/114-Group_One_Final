"""
@module main
@description FastAPI 應用程式入口點。
             前後端同機部署（ADR Q3），靜態前端檔案由 StaticFiles 掛載於 /。
             啟動時自動建立 SQLite 資料表並確保目錄存在。
@dependencies fastapi, uvicorn, core.config, models.db_models
@author 黃柏豪（後端 / 系統整合）
@version 1.1.0
"""

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import get_settings
from models.db_models import create_tables
from routers import upload, task, grade, student, log, auth, chat

# ── 日誌設定 ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()


# ── 應用程式生命週期 ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan：啟動時初始化資源，關閉時清理。"""
    # ── 啟動階段 ──────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("AI 課堂講義學習與複習規劃 Agent 後端啟動中...")
    logger.info("LLM 供應商：%s", settings.llm_provider)
    logger.info("ChromaDB 目錄：%s", settings.chroma_db_dir)
    logger.info("SQLite 路徑：%s", settings.database_url)

    # 建立必要目錄
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.chroma_db_dir, exist_ok=True)
    os.makedirs("frontend", exist_ok=True)  # 前端靜態檔目錄

    # 初始化 SQLite 資料表
    create_tables(settings.database_url)
    logger.info("SQLite 資料表初始化完成")
    logger.info("=" * 60)

    yield

    # ── 關閉階段 ──────────────────────────────────────────────────────────────
    logger.info("後端服務關閉中...")


# ── FastAPI 應用程式初始化 ─────────────────────────────────────────────────────
app = FastAPI(
    title="AI 課堂講義學習與複習規劃 Agent API",
    description=(
        "支援 PDF / PPT 講義上傳、AI 摘要、題目生成、批改、弱點分析與複習規劃。\n\n"
        "後端 / 系統整合負責人：黃柏豪 | 版本：v1.1.0"
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS 設定（開發模式允許所有來源，生產環境需收緊）─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境請改為具體前端網址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API 路由掛載 ───────────────────────────────────────────────────────────────
API_PREFIX = "/api"

app.include_router(auth.router,    prefix=API_PREFIX, tags=["Auth"])
app.include_router(upload.router,  prefix=API_PREFIX, tags=["Upload"])
app.include_router(task.router,    prefix=API_PREFIX, tags=["Task"])
app.include_router(grade.router,   prefix=API_PREFIX, tags=["Grade"])
app.include_router(student.router, prefix=API_PREFIX, tags=["Student"])
app.include_router(log.router,     prefix=API_PREFIX, tags=["Log"])
app.include_router(chat.router,    prefix=API_PREFIX, tags=["Chat"])


# ── 健康檢查端點 ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"], summary="健康檢查")
async def health_check():
    """確認後端服務正常運作。"""
    return {
        "status": "healthy",
        "version": "1.1.0",
        "llm_provider": settings.llm_provider,
    }


# ── 前端靜態檔掛載（ADR Q3：前後端同機）────────────────────────────────────
# FastAPI StaticFiles 服務前端 HTML/CSS/JS（所有 API 優先於靜態檔）
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    logger.info("前端靜態檔已掛載：%s", FRONTEND_DIR)
else:
    logger.warning("前端目錄不存在：%s（開發模式，僅提供 API）", FRONTEND_DIR)


# ── 主程式入口 ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,  # 開發模式熱重載
        log_level="info",
    )
