import re
import asyncio
from .base import BaseAgent
from backend.repositories.vector_repo import get_vector_repo
from backend.tools.rag_retriever import RAGRetriever as RealRAGRetriever
from backend.core.llm_client import get_llm_client

class RAGAgent(BaseAgent):
    """
    RAGAgent: 負責從講義知識庫（ChromaDB）中搜尋與檢索最相關的段落。
    對接實體 ChromaDB 向量庫，具備語意檢索與關鍵字混合評分（Hybrid Scoring）功能。
    """
    def __init__(self):
        super().__init__()
        # 初始化實體資料庫與檢索器
        self.vector_repo = get_vector_repo()
        self.llm_client = get_llm_client()
        self.retriever = RealRAGRetriever(self.vector_repo, self.llm_client)

    def add_to_knowledge_base(self, doc_name: str, doc_text: str):
        """
        將講義文字切分成包含頁碼資訊的 Chunks，並寫入實體 ChromaDB 向量庫與 SQLite。
        """
        # 依據 "第X頁：" 或換行分割簡報內容
        pages = re.split(r'(第\d+頁：)', doc_text)
        
        chunks = []
        if len(pages) <= 1:
            # Fallback 方案：若找不到頁碼標記，以雙換行切分
            chunks = [{"text": p.strip(), "page_num": 1} for p in doc_text.split("\n\n") if p.strip()]
        else:
            # 重組帶有頁碼標籤的頁面內容
            i = 0
            # 若第一頁標記前有文字，先將其加入第一頁
            if not pages[0].strip().startswith("第"):
                chunks.append({"text": pages[0].strip(), "page_num": 1})
                i = 1
            
            while i < len(pages) - 1:
                page_marker = pages[i]
                page_content = pages[i+1]
                
                # 從頁碼標記（例如 "第12頁："）中提取頁碼數字
                match = re.search(r'第(\d+)頁：', page_marker)
                page_num = int(match.group(1)) if match else 1
                
                chunks.append({
                    "text": f"{page_marker}\n{page_content.strip()}",
                    "page_num": page_num
                })
                i += 2
                
        # 呼叫非同步 index_document 方法寫入向量庫
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        try:
            if loop.is_running():
                # 若 loop 已經在運行，建立 task 並等待（有些環境下適用）
                count = loop.run_until_complete(
                    self.vector_repo.index_document(
                        document_id=doc_name,
                        student_id="default_student",
                        chunks=chunks
                    )
                )
            else:
                count = asyncio.run(
                    self.vector_repo.index_document(
                        document_id=doc_name,
                        student_id="default_student",
                        chunks=chunks
                    )
                )
            print(f"[RAGAgent] 成功將文件 '{doc_name}' 匯入實體向量庫，共建立 {count} 筆向量索引。")
        except Exception as e:
            print(f"[RAGAgent] 匯入向量庫失敗: {e}")

    def retrieve_content(self, query: str, top_k: int = 2) -> str:
        """
        真實語意檢索：透過 RAG 檢索器搜尋 ChromaDB，結合 Hybrid Scoring。
        """
        # 呼叫非同步 retrieve 進行檢索
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        try:
            if loop.is_running():
                passages = loop.run_until_complete(
                    self.retriever.retrieve(
                        instruction=query,
                        document_id=None,  # 設為 None 支援跨文件搜尋
                        top_k=top_k
                    )
                )
            else:
                passages = asyncio.run(
                    self.retriever.retrieve(
                        instruction=query,
                        document_id=None,
                        top_k=top_k
                    )
                )
        except Exception as e:
            print(f"[RAGAgent] 檢索失敗，將退回關鍵字 fallback 搜尋: {e}")
            return f"【RAGAgent 提示：檢索出錯：{e}】"

        if not passages:
            return f"【RAGAgent 提示：查無關於「{query}」的講義段落。】"
            
        # 格式化輸出檢索結果，印出正確的來源檔案與頁碼
        results = []
        for p in passages:
            page_info = f" (第 {p['page_num']} 頁)" if p.get("page_num") is not None else ""
            results.append(f"--- 來源檔案: {p['document_id']}{page_info} ---\n{p['text']}")
            
        return "\n\n".join(results)
