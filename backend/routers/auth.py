"""
@module routers.auth
@description 會員註冊、登入與認證路由。支援將訪客帳號連結升級為註冊帳號。
@dependencies fastapi, aiosqlite, bcrypt
@author Antigravity
@version 1.0.0
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
import logging
import bcrypt
import aiosqlite
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel, Field
from core.config import get_settings
from models.schemas import APIResponse, ErrorDetail

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 請求與回應結構 ───────────────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=50)
    student_name: str = Field("", max_length=100)
    student_id: str = Field("", description="選填，用於將既有訪客歷史紀錄綁定至此帳號")

class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=50)

# ── 輔助密碼安全與 Token 簽章工具 ───────────────────────────────────────────────

def hash_password(password: str) -> str:
    """單向 bcrypt 雜湊密碼"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    """驗證 bcrypt 密碼"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: dict, expires_in: int = 86400) -> str:
    """使用 HMAC-SHA256 生成安全的 Session Token"""
    settings = get_settings()
    secret_key = settings.secret_key
    payload = {
        "exp": int(time.time()) + expires_in,
        "data": data
    }
    payload_bytes = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(secret_key.encode(), payload_bytes.encode(), hashlib.sha256).hexdigest()
    return f"{payload_bytes}.{signature}"

def verify_access_token(token: str) -> Optional[dict]:
    """驗證 HMAC-SHA256 Session Token，過期或無效返回 None"""
    try:
        settings = get_settings()
        secret_key = settings.secret_key
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_bytes, signature = parts[0], parts[1]
        expected_signature = hmac.new(secret_key.encode(), payload_bytes.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None
        
        payload_json = base64.urlsafe_b64decode(payload_bytes.encode()).decode()
        payload = json.loads(payload_json)
        if time.time() > payload["exp"]:
            return None
        return payload["data"]
    except Exception:
        return None

# ── API 路由端點 ───────────────────────────────────────────────────────────────

@router.post(
    "/auth/register",
    response_model=APIResponse,
    summary="註冊會員 (或將訪客升級成會員)",
)
async def register(request: UserRegisterRequest):
    settings = get_settings()
    db_path = settings.database_url
    
    # 1. 檢查帳號是否已被註冊
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT student_id FROM students WHERE username = ?", (request.username,)
        ) as cursor:
            existing = await cursor.fetchone()
            if existing:
                return APIResponse(
                    status="error",
                    error=ErrorDetail(code="USERNAME_TAKEN", message="此帳號已有人使用")
                )
                
    password_hash = hash_password(request.password)
    target_student_id = request.student_id
    
    async with aiosqlite.connect(db_path) as db:
        if target_student_id:
            # 2. 升級訪客模式：檢查此訪客是否存在，且是否已被其他人綁定
            async with db.execute(
                "SELECT username FROM students WHERE student_id = ?", (target_student_id,)
            ) as cursor:
                student = await cursor.fetchone()
                if student:
                    # 已經存在該學生紀錄
                    stored_username = student[0]
                    if stored_username:
                        return APIResponse(
                            status="error",
                            error=ErrorDetail(code="VISITOR_BOUND", message="此訪客紀錄已被其他帳號綁定")
                        )
                    # 進行升級：更新現有欄位
                    await db.execute(
                        """
                        UPDATE students 
                        SET username = ?, password_hash = ?, student_name = ?, last_updated = ? 
                        WHERE student_id = ?
                        """,
                        (
                            request.username,
                            password_hash,
                            request.student_name or request.username,
                            time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                            target_student_id
                        )
                    )
                    await db.commit()
                    logger.info("[Auth] 訪客紀錄已升級為會員: %s (ID: %s)", request.username, target_student_id)
                else:
                    # 找不到該訪客，直接建立新的
                    target_student_id = str(uuid.uuid4())
                    await db.execute(
                        """
                        INSERT INTO students 
                        (student_id, username, password_hash, student_name, weak_topics, completed_chapters, preferred_quiz_type, last_updated)
                        VALUES (?, ?, ?, ?, '{}', '[]', 'multiple_choice', ?)
                        """,
                        (
                            target_student_id,
                            request.username,
                            password_hash,
                            request.student_name or request.username,
                            time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                        )
                    )
                    await db.commit()
                    logger.info("[Auth] 註冊新會員: %s (ID: %s)", request.username, target_student_id)
        else:
            # 3. 全新註冊
            target_student_id = str(uuid.uuid4())
            await db.execute(
                """
                INSERT INTO students 
                (student_id, username, password_hash, student_name, weak_topics, completed_chapters, preferred_quiz_type, last_updated)
                VALUES (?, ?, ?, ?, '{}', '[]', 'multiple_choice', ?)
                """,
                (
                    target_student_id,
                    request.username,
                    password_hash,
                    request.student_name or request.username,
                    time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                )
            )
            await db.commit()
            logger.info("[Auth] 註冊新會員: %s (ID: %s)", request.username, target_student_id)
            
    # 產生 Token
    token_data = {"student_id": target_student_id, "username": request.username}
    token = create_access_token(token_data)
    
    return APIResponse(
        status="success",
        data={
            "token": token,
            "student_id": target_student_id,
            "username": request.username
        }
    )

@router.post(
    "/auth/login",
    response_model=APIResponse,
    summary="會員登入",
)
async def login(request: UserLoginRequest):
    settings = get_settings()
    db_path = settings.database_url
    
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT student_id, password_hash, username FROM students WHERE username = ?", (request.username,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return APIResponse(
                    status="error",
                    error=ErrorDetail(code="INVALID_CREDENTIALS", message="帳號或密碼錯誤")
                )
                
            student_id = row["student_id"]
            password_hash = row["password_hash"]
            username = row["username"]
            
    if not password_hash or not verify_password(request.password, password_hash):
        return APIResponse(
            status="error",
            error=ErrorDetail(code="INVALID_CREDENTIALS", message="帳號或密碼錯誤")
        )
        
    # 產生 Token
    token_data = {"student_id": student_id, "username": username}
    token = create_access_token(token_data)
    
    return APIResponse(
        status="success",
        data={
            "token": token,
            "student_id": student_id,
            "username": username
        }
    )

@router.get(
    "/auth/me",
    response_model=APIResponse,
    summary="取得當前登入者資訊",
)
async def get_me(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return APIResponse(
            status="error",
            error=ErrorDetail(code="UNAUTHORIZED", message="請先登入系統")
        )
        
    token = authorization.split(" ")[1]
    data = verify_access_token(token)
    if not data:
        return APIResponse(
            status="error",
            error=ErrorDetail(code="TOKEN_EXPIRED", message="登入已逾期，請重新登入")
        )
        
    return APIResponse(
        status="success",
        data={
            "student_id": data["student_id"],
            "username": data["username"]
        }
    )
