"""
@module routers.chat
@description 講義 AI 隨身問答路由。提供 /api/chat 問答端點，
             結合 RAGRetriever 進行語意檢索與 LLMClient 生成解答。
@dependencies fastapi, tools.rag_retriever, core.llm_client, models.schemas
@author Antigravity
@version 1.0.0
"""

import logging
from typing import List, Optional
import aiosqlite
from fastapi import APIRouter, HTTPException, status

from core.config import get_settings
from core.llm_client import get_llm_client
from models.schemas import APIResponse, ChatRequest, ChatResponse
from repositories.vector_repo import get_vector_repo
from tools.rag_retriever import RAGRetriever

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

@router.post(
    "/chat",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="講義 AI 隨身問答",
    description="接收學生的提問，若提供 document_id 則使用 RAG 檢索相關講義內容並生成回答，否則進行一般領域問答。",
)
async def chat_with_lecture(request: ChatRequest):
    """
    處理講義問答對話。
    """
    logger.info(
        "[Router/chat] 收到對話請求：student_id=%s, doc_id=%s, message='%s'",
        request.student_id,
        request.document_id,
        request.message[:50]
    )

    llm_client = get_llm_client()
    provider = request.llm_provider or settings.llm_provider

    # 1. 處理 Mock 模式降級
    if provider == "mock":
        mock_answer = (
            f"【AI 隨身助教 - 模擬回答】\n"
            f"您好！目前系統運作於 Mock 模式。您詢問的問題是：\n"
            f"「{request.message}」\n\n"
            f"若您已設定真實的 Gemini 或 OpenAI API 金鑰，系統將會使用向量資料庫 (ChromaDB) 檢索您上傳的講義內容，"
            f"並為您生成高度相關且精準的繁體中文解析！"
        )
        return APIResponse(
            status="success",
            data=ChatResponse(
                answer=mock_answer,
                retrieved_passages=[]
            ).model_dump()
        )

    retrieved_passages = []
    
    # 2. 如果有傳入 document_id，進行 RAG 檢索
    if request.document_id:
        try:
            vector_repo = get_vector_repo()
            retriever = RAGRetriever(vector_repo, llm_client)
            retrieved_passages = await retriever.retrieve(
                instruction=request.message,
                document_id=request.document_id,
                top_k=4  # 檢索前 4 個相關段落
            )
        except Exception as exc:
            logger.error("[Router/chat] RAG 檢索失敗，將降級為直接問答：%s", exc)

    # 3. 根據有無檢索到內容，建構 Prompt
    if retrieved_passages:
        context_text = "\n\n".join(
            f"[段落 {i+1}]: {p['text']}" for i, p in enumerate(retrieved_passages)
        )
        
        system_prompt = (
            "你是一個專業的課堂學習隨身 AI 助教。請用繁體中文回應學生。\n"
            "以下是從學生上傳的課堂講義中檢索出來的相關參考內容片段：\n"
            "--------------------\n"
            f"{context_text}\n"
            "--------------------\n"
            "請嚴格根據上面的講義片段，詳細、親切且有條理地回答學生的問題。\n"
            "規範限制：\n"
            "1. 優先且主要使用講義中的內容來回答。\n"
            "2. 如果講義中的內容不足以完全解答，可以基於該學術領域進行專業補充，但必須在補充的部分明確說明『（以下為講義外的補充資訊）』。\n"
            "3. 如果學生問了完全與講義主題無關的問題（例如問日常聊天或程式笑話），請禮貌地引導學生回到講義內容的學習上。"
        )
        
        prompt = f"學生的問題是：\"{request.message}\"\n請幫忙解答並給出引導性的複習建議。"
    else:
        # 沒有 document_id，或檢索為空
        system_prompt = (
            "你是一個專業的課堂學習隨身 AI 助教。請用繁體中文回應學生。\n"
            "目前學生未指定講義文件或講義中查無此內容，請作為該學術領域的專家進行解答。\n"
            "規範限制：\n"
            "1. 回答口吻要親切、具有啟發性，並層次分明。\n"
            "2. 鼓勵學生上傳相關課堂講義，以便獲得更精準的針對性解答。"
        )
        prompt = request.message

    # 4. 呼叫 LLM 生成回答
    try:
        answer = await llm_client.complete(
            prompt=prompt,
            provider=provider,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1500
        )
        
        return APIResponse(
            status="success",
            data=ChatResponse(
                answer=answer,
                retrieved_passages=retrieved_passages
            ).model_dump()
        )
    except Exception as exc:
        logger.error("[Router/chat] LLM 生成回答失敗：%s", exc)
        return APIResponse(
            status="error",
            error={"code": "CHAT_GENERATION_FAILED", "message": f"AI 生成回答失敗：{exc}"}
        )
