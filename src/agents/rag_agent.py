import re
from .base import BaseAgent

class RAGAgent(BaseAgent):
    """
    RAGAgent: Responsible for searching and retrieving relevant paragraphs from the lecture knowledge base.
    Input: User question or topic.
    Output: Relevant chunks/paragraphs from the lecture slides.
    """
    def __init__(self):
        super().__init__()
        # Internal simple store for the knowledge base
        # Format: { doc_name: [list of paragraphs/pages] }
        self.knowledge_base = {}

    def add_to_knowledge_base(self, doc_name: str, doc_text: str):
        """
        Splits the document text into pages or chunks and stores them.
        """
        # Split by "第X頁：" or simple double newlines to segment the content
        pages = re.split(r'(第\d+頁：)', doc_text)
        
        chunks = []
        if len(pages) <= 1:
            # Fallback if no page marker found: split by double newlines
            chunks = [p.strip() for p in doc_text.split("\n\n") if p.strip()]
        else:
            # Reconstruct pages with their headers
            i = 0
            # If the text starts with a header before the first page marker, capture it
            if not pages[0].strip().startswith("第"):
                chunks.append(pages[0].strip())
                i = 1
            
            while i < len(pages) - 1:
                page_marker = pages[i]
                page_content = pages[i+1]
                chunks.append(f"{page_marker}\n{page_content.strip()}")
                i += 2
                
        self.knowledge_base[doc_name] = chunks
        print(f"[RAGAgent] 已將文件 '{doc_name}' 匯入知識庫，共切分為 {len(chunks)} 個段落。")

    def retrieve_content(self, query: str, top_k: int = 2) -> str:
        """
        Mock search: Find top_k paragraphs containing the query keywords.
        """
        if not self.knowledge_base:
            return "【RAGAgent 提示：知識庫目前為空，請先上傳/讀取講義檔案。】"
        
        # Simple keyword matching
        keywords = [kw.lower() for kw in re.findall(r'\w+', query) if len(kw) > 1]
        if not keywords:
            # Fallback to query itself
            keywords = [query.lower()]
            
        matched_chunks = []
        for doc_name, chunks in self.knowledge_base.items():
            for chunk in chunks:
                score = 0
                for kw in keywords:
                    if kw in chunk.lower():
                        score += 1
                
                if score > 0:
                    matched_chunks.append({
                        "doc_name": doc_name,
                        "content": chunk,
                        "score": score
                    })
        
        # Sort matched chunks by score descending
        matched_chunks.sort(key=lambda x: x["score"], reverse=True)
        
        if not matched_chunks:
            # If no matches, return a default selection or warning
            return f"【RAGAgent 提示：查無關於「{query}」的講義段落。】"
            
        # Get top-k contents and format output
        results = []
        for match in matched_chunks[:top_k]:
            results.append(f"--- 來源檔案: {match['doc_name']} ---\n{match['content']}")
            
        return "\n\n".join(results)
