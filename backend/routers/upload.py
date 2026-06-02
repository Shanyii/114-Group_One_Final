"""
@module routers.upload
@description 檔案上傳路由。接收 PDF / PPTX 講義，解析後存入 DB 並建立 ChromaDB 向量索引。
@dependencies fastapi, tools.document_parser, repositories.vector_repo
@author 黃柏豪（後端 / 系統整合）
@version 1.1.0
"""

import logging
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from models.schemas import APIResponse, UploadResponse
from tools.document_parser import DocumentParser
from repositories.vector_repo import get_vector_repo

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 路由：POST /api/upload ─────────────────────────────────────────────────────
@router.post(
    "/upload",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="上傳講義檔案",
    description="接收 PDF 或 PPTX 講義，解析純文字並建立 ChromaDB 向量索引。返回 document_id 供後續任務引用。",
)
async def upload_document(
    file: UploadFile = File(..., description="講義檔案（PDF 或 PPTX，最大 50MB）"),
    student_id: str = Form(..., description="學生 UUID（前端 crypto.randomUUID() 生成）"),
):
    """
    上傳並解析講義。

    Args:
        file: 上傳的 PDF / PPTX 檔案
        student_id: 學生 UUID

    Returns:
        APIResponse: 包含 document_id 的成功回應

    Raises:
        422: 學生 ID 格式錯誤
        400: 檔案格式不支援或超過大小限制
        500: 解析或索引建立失敗
    """
    # 驗證 student_id UUID 格式
    try:
        uuid.UUID(student_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="student_id 必須為合法的 UUID 格式",
        )

    # 讀取檔案內容
    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"讀取檔案失敗：{exc}",
        )

    # 解析文件並存入 DB
    parser = DocumentParser()
    try:
        document_id = await parser.save_and_parse(
            file_bytes=file_bytes,
            filename=file.filename or "unknown",
            student_id=student_id,
            content_type=file.content_type or "",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("[Router/upload] 文件解析失敗：%s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件解析失敗，請稍後重試",
        )

    # 建立 ChromaDB 向量索引（背景建立，可選等待）
    try:
        chunks = await parser.get_chunks(document_id)
        vector_repo = get_vector_repo()
        indexed_count = await vector_repo.index_document(document_id, student_id, chunks)
        logger.info("[Router/upload] 向量索引建立完成：doc_id=%s, chunks=%d", document_id, indexed_count)
    except Exception as exc:
        # 索引失敗不阻斷上傳（降級處理）
        logger.error("[Router/upload] 向量索引建立失敗（不影響上傳）：%s", exc)

    file_type = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "unknown"
    return APIResponse(
        status="success",
        data=UploadResponse(
            document_id=document_id,
            filename=file.filename or "unknown",
            file_type=file_type,
        ).model_dump(),
    )
