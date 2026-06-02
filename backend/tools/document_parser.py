"""
@module document_parser
@description 文件解析工具。支援 PDF（pdfplumber）與 PPT/PPTX（python-pptx）格式，
             解析後依 config.chunk_size 切分為 Chunk，供 RAG 向量化使用。
@dependencies pdfplumber, python-pptx, core.config
@author 楊沁霖（RAG / 資料處理）
@version 1.1.0
"""

import logging
import os
import uuid
from pathlib import Path

import aiosqlite
import pdfplumber
from pptx import Presentation

from core.config import get_settings

logger = logging.getLogger(__name__)

# ── 支援的 MIME Type 白名單 ───────────────────────────────────────────────────
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.ms-powerpoint": "pptx",
}

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class DocumentParser:
    """
    文件解析工具。

    負責：
    1. 驗證並儲存上傳檔案（至 uploads/ 暫存目錄）
    2. 解析 PDF / PPT 為純文字
    3. 切分文字為 Chunk 列表（用於 Embedding）
    4. 將解析結果存入 SQLite documents 資料表

    Example:
        >>> parser = DocumentParser()
        >>> doc_id = await parser.save_and_parse(file_bytes, "lecture.pdf", student_id)
        >>> chunks = await parser.get_chunks(doc_id)
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    async def save_and_parse(
        self,
        file_bytes: bytes,
        filename: str,
        student_id: str,
        content_type: str,
    ) -> str:
        """
        儲存上傳檔案並解析為純文字，存入資料庫。

        Args:
            file_bytes: 上傳檔案的二進位內容
            filename: 原始檔案名稱
            student_id: 學生 UUID
            content_type: MIME Type

        Returns:
            str: 生成的 document_id（UUID）

        Raises:
            ValueError: 檔案格式不支援或超過大小限制
        """
        # 驗證檔案大小
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"檔案大小超過限制（最大 50MB），目前：{len(file_bytes) / 1024 / 1024:.1f}MB")

        # 驗證 MIME Type
        file_type = ALLOWED_MIME_TYPES.get(content_type)
        if file_type is None:
            raise ValueError(f"不支援的檔案格式：{content_type}。僅接受 PDF 與 PPTX")

        document_id = str(uuid.uuid4())

        # 暫存至 uploads 目錄
        temp_path = os.path.join(self.settings.upload_dir, f"{document_id}.{file_type}")
        os.makedirs(self.settings.upload_dir, exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        # 解析純文字
        try:
            raw_text = self._parse_file(temp_path, file_type)
        finally:
            # 解析完成後刪除暫存檔（不長期儲存原始講義）
            if os.path.exists(temp_path):
                os.remove(temp_path)

        if not raw_text.strip():
            raise ValueError("無法從檔案中提取文字內容，請確認檔案未加密或非空白")

        # 存入資料庫
        await self._save_to_db(document_id, student_id, filename, file_type, raw_text)
        logger.info("[DocParser] 文件解析完成：doc_id=%s, 字元數=%d", document_id, len(raw_text))
        return document_id

    def _parse_file(self, file_path: str, file_type: str) -> str:
        """
        依檔案類型解析純文字。

        Args:
            file_path: 暫存檔案路徑
            file_type: 'pdf' | 'pptx'

        Returns:
            str: 提取的純文字
        """
        if file_type == "pdf":
            return self._parse_pdf(file_path)
        elif file_type == "pptx":
            return self._parse_pptx(file_path)
        raise ValueError(f"未知的檔案類型：{file_type}")

    def _parse_pdf(self, file_path: str) -> str:
        """使用 pdfplumber 提取 PDF 文字（支援中文）。"""
        texts = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text(x_tolerance=3, y_tolerance=3)
                    if text:
                        texts.append(f"--- 第 {page_num} 頁 ---\n{text}")
        except Exception as exc:
            raise ValueError(f"PDF 解析失敗：{exc}") from exc
        return "\n\n".join(texts)

    def _parse_pptx(self, file_path: str) -> str:
        """使用 python-pptx 提取簡報文字。"""
        texts = []
        try:
            prs = Presentation(file_path)
            for slide_num, slide in enumerate(prs.slides, 1):
                slide_texts = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text.strip())
                if slide_texts:
                    texts.append(f"--- 第 {slide_num} 張投影片 ---\n" + "\n".join(slide_texts))
        except Exception as exc:
            raise ValueError(f"PPTX 解析失敗：{exc}") from exc
        return "\n\n".join(texts)

    def chunk_text(self, text: str) -> list[str]:
        """
        將純文字切分為固定大小的 Chunk（有重疊）。

        Args:
            text: 原始純文字

        Returns:
            list[str]: Chunk 列表（非空）
        """
        chunk_size = self.settings.chunk_size
        overlap = self.settings.chunk_overlap
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
        logger.debug("[DocParser] 切分完成：%d 個 Chunks", len(chunks))
        return chunks

    async def read_from_db(self, document_id: str) -> str:
        """
        從資料庫讀取文件純文字。

        Args:
            document_id: 文件 UUID

        Returns:
            str: 純文字內容

        Raises:
            ValueError: 文件不存在
        """
        async with aiosqlite.connect(self.settings.database_url) as db:
            async with db.execute(
                "SELECT raw_text FROM documents WHERE document_id = ?", (document_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None or not row[0]:
                    raise ValueError(f"找不到文件或文字為空：{document_id}")
                return row[0]

    async def get_chunks(self, document_id: str) -> list[str]:
        """
        取得文件的 Chunk 列表（從 DB 讀取後切分）。

        Args:
            document_id: 文件 UUID

        Returns:
            list[str]: Chunk 列表
        """
        raw_text = await self.read_from_db(document_id)
        return self.chunk_text(raw_text)

    async def _save_to_db(
        self,
        document_id: str,
        student_id: str,
        filename: str,
        file_type: str,
        raw_text: str,
    ) -> None:
        """將解析結果存入 documents 資料表。"""
        from datetime import datetime
        async with aiosqlite.connect(self.settings.database_url) as db:
            await db.execute(
                """
                INSERT INTO documents
                (document_id, student_id, filename, file_type, raw_text, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (document_id, student_id, filename, file_type, raw_text,
                 datetime.utcnow().isoformat()),
            )
            await db.commit()
