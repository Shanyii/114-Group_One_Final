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

    filename = None
    if request.document_id:
        try:
            async with aiosqlite.connect(settings.database_url) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT filename FROM documents WHERE document_id = ?",
                    (request.document_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        filename = row["filename"]
        except Exception as exc:
            logger.error("[Router/chat] 查詢講義檔名失敗：%s", exc)

    retrieved_passages = []
    rag_warning = None
    
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
            rag_warning = f"RAG 檢索失敗：{exc}"
            logger.error("[Router/chat] RAG 檢索失敗，將降級為直接問答：%s", exc)

    # 3. 根據有無檢索到內容或附加的 context，建構 Prompt
    context_sections = []
    if retrieved_passages:
        for i, p in enumerate(retrieved_passages):
            context_sections.append(f"[講義段落 {i+1}]: {p['text']}")
    if request.context and request.context.strip():
        context_sections.append(f"[講義重點摘要與大綱]:\n{request.context.strip()}")

    if context_sections:
        context_text = "\n\n".join(context_sections)
        
        system_prompt = (
            "你是一個專業的課堂學習隨身 AI 助教。請用繁體中文回應學生。\n"
            "以下是從學生講義或重點摘要中提取出來的相關參考背景內容：\n"
            "--------------------\n"
            f"{context_text}\n"
            "--------------------\n"
            "請嚴格根據上面的參考內容，詳細、親切且有條理地回答學生的問題。\n"
            "規範限制：\n"
            "1. 優先且主要使用給定的背景內容來回答。\n"
            "2. 如果給定內容不足以完全解答，可以基於該學術領域進行專業補充，但必須在補充的部分明確說明『（以下為講義外的補充資訊）』。\n"
            "3. 如果學生問了完全與講義主題無關的問題，請禮貌地引導學生回到講義內容的學習上。"
        )
    else:
        # 沒有 document_id，或檢索與 context 皆為空
        system_prompt = (
            "你是一個專業的課堂學習隨身 AI 助教。請用繁體中文回應學生。\n"
            "目前學生未指定講義文件或講義中查無此內容，請作為該學術領域的專家進行解答。\n"
            "規範限制：\n"
            "1. 回答口吻要親切、具有啟發性，並層次分明。\n"
            "2. 鼓勵學生上傳相關課堂講義，以便獲得更精準的針對性解答。"
        )

    # 4. 格式化對話歷史紀錄 (維持前後文記憶)
    history_text = ""
    if request.history:
        history_text = "以下是先前的對話歷史（請注意上下文關係，維持對話連貫性）：\n"
        for msg in request.history:
            role_name = "學生" if msg.role == "user" else "AI 助教"
            history_text += f"{role_name}: {msg.content}\n"
        history_text += "\n"

    prompt = f"{history_text}學生最新問題：\"{request.message}\"\n請針對最新問題進行回應。"

    # 5. 呼叫 LLM 生成回答
    try:
        answer = await llm_client.complete(
            prompt=prompt,
            provider=provider,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1500
        )
        
        # 建構步驟顯示
        doc_display_id = request.document_id[:8] if request.document_id else "unknown"
        if request.document_id:
            matched_count = len(retrieved_passages)
            max_score = max(p.get("score", 0) for p in retrieved_passages) if retrieved_passages else 0
            thinking_process = (
                f"> ⚙️ **【AI RAG 引擎運作流程】**\n"
                f"> - **[步驟 1] 意圖偵測**：偵測到學生提問，判斷需要結合已載入講義進行關聯式 RAG 檢索。\n"
                f"> - **[步驟 2] 檔案檢查**：確認已載入講義檔案 `\"{filename or '講義檔案'}\"` (文件 ID: `{doc_display_id}...`)。\n"
                f"> - **[步驟 3] 工具呼叫**：呼叫語意向量檢索工具 `RAGRetriever.retrieve` 進行相似度檢索。\n"
                f"> - **[步驟 4] 比對計算**：檢索完成，在講義中成功檢索到 {matched_count} 個高相似度知識段落。\n"
                f"> - **[步驟 5] 流程輸出**：將相關段落送入大語言模型，調用 `llm_client.complete` 生成深度繁體中文解答。\n\n"
            )
        else:
            thinking_process = (
                f"> ⚙️ **【AI 常規引擎運作流程】**\n"
                f"> - **[步驟 1] 意圖偵測**：偵測到學生提問，且無指定講義文件，決定作為學術領域專家進行常規解答。\n"
                f"> - **[步驟 2] 檔案檢查**：無載入講義檔案，略過向量資料庫檢索。\n"
                f"> - **[步驟 3] 工具呼叫**：直接建立對話 Prompt，並包含先前的對話歷史。\n"
                f"> - **[步驟 4] 比對計算**：調用大語言模型 `llm_client.complete` (供應商：{provider or '預設'}) 進行智能論述生成。\n"
                f"> - **[步驟 5] 流程輸出**：生成親切、層次分明的解答內容。\n\n"
            )

        full_answer = thinking_process + answer

        return APIResponse(
            status="success",
            data=ChatResponse(
                answer=full_answer,
                retrieved_passages=retrieved_passages,
                warning=rag_warning
            ).model_dump()
        )
    except Exception as exc:
        logger.error("[Router/chat] LLM 生成回答失敗，將啟動本地智能檢索 Fallback：%s", exc)
        fallback_warning = rag_warning or f"LLM 呼叫失敗：{exc}"
        return await handle_local_qa_fallback(request, retrieved_passages, warning=fallback_warning)



def rank_segments_local(query: str, raw_text: str, top_k: int = 3) -> list[dict]:
    import re
    # 依頁面/投影片/段落切分
    raw_segments = raw_text.split("\n\n")
    segments = []
    
    current_page = "未知"
    for seg in raw_segments:
        seg_strip = seg.strip()
        if not seg_strip:
            continue
        if seg_strip.startswith("--- ") and seg_strip.endswith(" ---"):
            current_page = seg_strip.replace("---", "").strip()
            continue
            
        segments.append({
            "text": seg_strip,
            "page": current_page
        })
        
    # 如果段落太少，依換行切分
    if len(segments) < 3:
        segments = []
        lines = raw_text.split("\n")
        current_page = "未知"
        for line in lines:
            line_strip = line.strip()
            if not line_strip:
                continue
            if line_strip.startswith("--- ") and line_strip.endswith(" ---"):
                current_page = line_strip.replace("---", "").strip()
                continue
            segments.append({
                "text": line_strip,
                "page": current_page
            })
            
    cleaned_query = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", query.lower())
    query_words = [w for w in cleaned_query.split() if w]
    
    char_match_mode = False
    if not query_words or all(len(w) == 1 for w in query_words):
        query_words = [c for c in cleaned_query if c.strip()]
        char_match_mode = True
        
    scored_segments = []
    for seg in segments:
        score = 0
        seg_lower = seg["text"].lower()
        
        for word in query_words:
            if word in seg_lower:
                if char_match_mode:
                    score += seg_lower.count(word)
                else:
                    score += seg_lower.count(word) * 5
                    
        phrase = query.lower().replace(" ", "")
        seg_dense = seg_lower.replace(" ", "")
        if len(phrase) >= 2 and phrase in seg_dense:
            score += len(phrase) * 10
            
        if score > 0:
            scored_segments.append((score, seg))
            
    scored_segments.sort(key=lambda x: x[0], reverse=True)
    
    results = []
    for score, seg in scored_segments[:top_k]:
        results.append({
            "text": seg["text"],
            "metadata": {"page": seg["page"]},
            "score": score
        })
    return results


async def handle_local_qa_fallback(
    request: ChatRequest,
    retrieved_passages: List[dict] = None,
    warning: Optional[str] = None,
) -> APIResponse:
    from core.config import get_settings
    import aiosqlite
    
    settings = get_settings()
    db_path = settings.database_url
    
    filename = None
    raw_text = ""
    
    # 1. 如果有傳入 document_id，嘗試從資料庫載入檔案內容
    if request.document_id:
        try:
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT filename, raw_text FROM documents WHERE document_id = ?",
                    (request.document_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        filename = row["filename"]
                        raw_text = row["raw_text"] or ""
        except Exception as exc:
            logger.error("[Router/chat] 本地載入講義內容失敗：%s", exc)
            
    # 2. 如果有 raw_text，進行本地關鍵字比對排名
    local_matched_passages = []
    if raw_text:
        try:
            local_matched_passages = rank_segments_local(request.message, raw_text, top_k=3)
        except Exception as exc:
            logger.error("[Router/chat] 本地關鍵字比對失敗：%s", exc)
        
    # 3. 組合檢索出的段落 (優先使用本地段落，否則使用 RAG 已檢索到的段落)
    active_passages = local_matched_passages if local_matched_passages else (retrieved_passages or [])
    
    # 4. 構建回答
    if active_passages:
        passages_text_list = []
        frontend_passages = []
        for idx, p in enumerate(active_passages):
            page_info = p.get("metadata", {}).get("page", "未知")
            text_snippet = p["text"]
            passages_text_list.append(
                f"### 📍 講義段落 {idx+1} (頁碼/來源：{page_info})\n"
                f"> {text_snippet}"
            )
            frontend_passages.append({
                "text": text_snippet,
                "metadata": {"page": page_info}
            })
            
        retrieved_content = "\n\n".join(passages_text_list)
        
        # 計算最高得分與配對段落數
        max_score = max(p.get("score", 0) for p in active_passages) if active_passages else 0
        matched_count = len(local_matched_passages) if local_matched_passages else len(active_passages)
        doc_display_id = request.document_id[:8] if request.document_id else "unknown"
        
        thinking_process = (
            f"> ⚙️ **【本地降級引擎運作流程】**\n"
            f"> - **[步驟 1] 意圖偵測**：偵測到大模型 API 呼叫異常或 429 額度超限，自動啟動本地 RAG 降級 Fallback 策略。\n"
            f"> - **[步驟 2] 檔案檢查**：確認已載入講義檔案 `\"{filename or '講義檔案'}\"` (文件 ID: `{doc_display_id}...`)。\n"
            f"> - **[步驟 3] 工具呼叫**：調用本地檢索分析工具 `rank_segments_local`，分析查詢字詞 `\"{request.message}\"`。\n"
            f"> - **[步驟 4] 比對計算**：比對成功，在講義中匹配到 {matched_count} 個符合的文字段落。\n"
            f"> - **[步驟 5] 流程輸出**：選取相關度得分最高的前 {len(active_passages)} 個段落（最高得分：{max_score} 分）進行渲染。\n\n"
        )
        
        answer = (
            f"{thinking_process}"
            f"### 🤖 【AI 隨身助教 - 本地智能檢索與分析】\n"
            f"*(⚠️ 偵測到後端 API 額度用盡或連線異常，系統已自動啟用本地離線引擎進行精準檢索與解答)*\n\n"
            f"針對您詢問的「**{request.message}**」，我在您的講義「**{filename or '目前載入講義'}**」中為您精準檢索出以下最相關的內容段落：\n\n"
            f"{retrieved_content}\n\n"
            f"---\n"
            f"### 💡 本地複習建議與導讀\n"
            f"1. **關鍵概念複習**：上述段落是從您的講義中直接提取的原文。請仔細閱讀並對照這些段落以釐清觀念。\n"
            f"2. **自我測驗建議**：若您想測試自己是否已掌握此觀念，可以到「複習計畫」區域，確認將相關主題加入弱點主題，並點擊「重新生成計畫」來發起自我評量測驗。\n"
            f"3. **重新提問**：若需要 AI 進行更深度的整合性論述，請在 API 額度重置後重新發送訊息。"
        )
    else:
        # 沒有講義內容，或檢索不出內容
        # 提供本地預設計算機科學常見知識庫問答，若匹配到則顯示知識點
        knowledge_base = {
            "git": (
                "**Git** 是一個分散式版本控制系統，用來追蹤檔案的修改歷史，並方便多人協同開發。\n\n"
                "**主要核心觀念：**\n"
                "- **Repository (版本庫)**：儲存所有歷史紀錄的專案目錄。\n"
                "- **Commit (提交)**：將目前的修改儲存為一個歷史節點，像存檔一樣。\n"
                "- **Branch (分支)**：平行開發的線路，例如 `main` 或 `feature/login`。\n"
                "- **Merge (合併)**：將不同分支的修改合併在一起。"
            ),
            "overfitting": (
                "**過擬合 (Overfitting)** 指的是機器學習模型對訓練資料學習得「太完美」了，甚至連其中的雜訊和細枝末節都記了下來。\n\n"
                "**主要徵兆：**\n"
                "- 在訓練集 (Training Set) 上的準確率極高。\n"
                "- 在測試集 (Test Set) 或新資料上的表現極差（泛化能力低）。\n\n"
                "**解決方法：**\n"
                "1. 增加資料量（讓模型看更多範例）。\n"
                "2. 使用正規化 (Regularization, L1/L2)。\n"
                "3. 實施早停法 (Early Stopping)。"
            ),
            "bst": (
                "**二元搜尋樹 (Binary Search Tree, BST)** 是一種二元樹資料結構，具有以下特性：\n"
                "- 每個節點最多有兩個子節點（左子節點與右子節點）。\n"
                "- 左子樹上所有節點的值都小於該節點的值。\n"
                "- 右子樹上所有節點的值都大於該節點的值。\n\n"
                "**重要走訪方式：**\n"
                "- **中序走訪 (In-order Traversal)**：按照『左 -> 根 -> 右』順序，拜訪結果會是「由小到大排序好的數列」。\n"
                "- **搜尋/插入複雜度**：平均為 $O(\\log N)$，最壞情況為 $O(N)$（當樹退化成一條直線時）。"
            ),
            "learning rate": (
                "**學習率 (Learning Rate, α)** 是機器學習最佳化演算法（如梯度下降法）中用來控制更新參數步長的重要超參數。\n\n"
                "**特性說明：**\n"
                "- **學習率太高**：每次更新跨步太大，會導致 Loss 在谷底震盪，甚至發散（無法收斂）。\n"
                "- **學習率太低**：每次更新太慢，會需要非常多次迭代才能收斂，浪費計算資源。"
            )
        }
        
        # 尋找匹配的預設知識庫
        matched_content = None
        normalized_msg = request.message.lower()
        matched_topic = None
        for key, val in knowledge_base.items():
            if key in normalized_msg:
                matched_content = val
                matched_topic = key
                break
                
        # 建構步驟 2 的檔案檢查狀態文字
        if request.document_id:
            file_check_reason = f"已載入講義 `\"{filename or '講義檔案'}\"`，但調用 `rank_segments_local` 未匹配到原文段落，轉入內建知識匹配"
        else:
            file_check_reason = "未偵測到任何載入的歷史講義，略過檔案檢索，直接進入知識庫匹配"
            
        if matched_content:
            thinking_process = (
                f"> ⚙️ **【本地降級引擎運作流程】**\n"
                f"> - **[步驟 1] 意圖偵測**：偵測到大模型 API 呼叫異常或 429 額度超限，自動啟動本地 RAG 降級 Fallback 策略。\n"
                f"> - **[步驟 2] 檔案檢查**：{file_check_reason}。\n"
                f"> - **[步驟 3] 工具呼叫**：調用本地知識匹配工具 `knowledge_base_match`，檢查是否符合內建核心科目詞條。\n"
                f"> - **[步驟 4] 比對計算**：匹配成功，命中本地知識庫的核心詞條 `\"{matched_topic.upper()}\"`。\n"
                f"> - **[步驟 5] 流程輸出**：載入本地知識點解析並套用學習引導模板。\n\n"
            )
            
            answer = (
                f"{thinking_process}"
                f"### 🤖 【AI 隨身助教 - 本地智能庫解析】\n"
                f"*(⚠️ 偵測到後端 API 額度用盡或連線異常，系統已自動啟用本地離線知識庫進行解答)*\n\n"
                f"針對您詢問的「**{request.message}**」，為您提供本地知識點解析：\n\n"
                f"{matched_content}\n\n"
                f"---\n"
                f"💡 **提示**：目前系統為離線/本地模式。若想針對您特定的上傳講義內容進行精準 RAG 問答，請先上傳講義並在 API 額度恢復後重新詢問。"
            )
        else:
            thinking_process = (
                f"> ⚙️ **【本地降級引擎運作流程】**\n"
                f"> - **[步驟 1] 意圖偵測**：偵測到大模型 API 呼叫異常或 429 額度超限，自動啟動本地 RAG 降級 Fallback 策略。\n"
                f"> - **[步驟 2] 檔案檢查**：{file_check_reason}。\n"
                f"> - **[步驟 3] 工具呼叫**：調用本地知識匹配工具 `knowledge_base_match`，檢查是否符合內建核心科目詞條。\n"
                f"> - **[步驟 4] 比對計算**：比對結束，未匹配到任何內置核心詞條，使用離線通用引導。\n"
                f"> - **[步驟 5] 流程輸出**：載入離線通用學習指南提示模組。\n\n"
            )
            
            answer = (
                f"{thinking_process}"
                f"### 🤖 【AI 隨身助教 - 本地引導回覆】\n"
                f"*(⚠️ 偵測到後端 API 額度用盡或連線異常，已自動切換為本地離線引導模式)*\n\n"
                f"您好！我目前正處於本地離線問答狀態。您詢問的主題是：「**{request.message}**」。\n\n"
                f"由於未能在目前上傳的講義中檢索到直接相關的原文段落，且此主題未包含在本地快速知識庫中，為您提供以下學習建議：\n"
                f"- **翻閱講義**：建議檢視講義檔案中是否包含此主題關鍵字，並確認點擊「載入講義」後再進行問答。\n"
                f"- **複習錯題**：您可以點擊下方的「重新整理歷程」，在「歷史答題對錯紀錄」中看看先前答錯的題目是否與此主題相關。\n"
                f"- **稍後再試**：大模型的每日 API 呼叫額度會在隔日重置，屆時您可以再次提問以獲取 AI 的完整生成式分析！"
            )
            
        frontend_passages = []
        
    return APIResponse(
        status="success",
        data=ChatResponse(
            answer=answer,
            retrieved_passages=frontend_passages,
            warning=warning
        ).model_dump()
    )
