from src.agents.rag_agent import RAGAgent

# Instantiate the RAGAgent
_rag_agent = RAGAgent()

def retrieve_content(query: str) -> str:
    """
    從講義知識庫查詢相關段落（RAG）。
    輸入：使用者問題 / 主題 (str)
    輸出：相關講義內容段落 (str)
    觸發時機：使用者詢問或需要生成內容時
    """
    return _rag_agent.retrieve_content(query)

def add_to_knowledge_base(doc_name: str, doc_text: str) -> None:
    """
    Helper function to feed parsed content into the RAG knowledge base.
    """
    _rag_agent.add_to_knowledge_base(doc_name, doc_text)
