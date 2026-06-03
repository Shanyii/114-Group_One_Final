from .base import BaseAgent

class SummaryAgent(BaseAgent):
    """
    SummaryAgent: Responsible for generating clear, structured markdown summaries of lecture sections.
    Input: User query / theme and the retrieved lecture paragraphs (RAG Context).
    Output: Markdown structured summary.
    """
    def __init__(self):
        super().__init__()
        try:
            self.template = self.load_prompt_template("summary_agent.txt")
        except FileNotFoundError:
            # Fallback template if prompt file is not found
            self.template = "請整理以下講義重點：\n主題: {{ USER_QUERY }}\n內容:\n{{ RAG_CONTEXT }}"

    def generate_summary(self, query: str, rag_context: str) -> str:
        """
        Generates a summary based on user query and retrieved context.
        Calls Gemini API if available, otherwise falls back to a simulated response.
        """
        # Format prompt template
        prompt = self.format_prompt(
            self.template,
            USER_QUERY=query,
            RAG_CONTEXT=rag_context
        )
        
        # Check if client is initialized
        if not self.client:
            print("[SummaryAgent] 提示: 未偵測到 GEMINI_API_KEY，將啟用本地模擬回覆。")
            return self._mock_summary(query, rag_context)
            
        try:
            # Call Google GenAI SDK (Gemini 2.5 Flash)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"[SummaryAgent] API 呼叫失敗: {e}。切換至本地模擬回覆。")
            return self._mock_summary(query, rag_context)

    def _mock_summary(self, query: str, context: str) -> str:
        """
        Simulated offline summary response if Gemini API key is missing.
        """
        if not context or context.startswith("【RAGAgent"):
            context = "自然語言處理簡介\n第一頁：\n什麼是自然語言處理 (NLP)？\n- 定義：資訊科學與人類語言交互的學科。\n第二頁：\nNLP 的挑戰：\n- 歧義性：同一個詞在不同語境下有不同意思。"
            
        if "tf-idf" in query.lower() or "tfidf" in query.lower():
            return r"""# 🎯 【模擬輸出】TF-IDF 知識重點整理

這是因為您未設定 `GEMINI_API_KEY` 所產生的模擬結果。設定 Key 後將可獲得 AI 生成的真實內容！

## 1. 詞頻 (Term Frequency, TF)
* **定義**：一個詞彙在單一文件中出現的頻率。 [來源: nlp_chapter3.pdf 第5頁]
* **公式**：
  $$TF(t, d) = \frac{f_{t,d}}{\sum_{t'} f_{t',d}}$$

## 2. 逆文件頻率 (Inverse Document Frequency, IDF)
* **定義**：衡量詞彙在整體文件庫中的代表性。 [來源: nlp_chapter3.pdf 第12頁]
* **公式**：
  $$IDF(t, D) = \log\left(\frac{N}{|\{d \in D : t \in d\}|}\right)$$

---
* 備註：模擬完成。如需真實 AI 整理，請在 `.env` 中設定 `GEMINI_API_KEY`。
"""
        elif "pcfg" in query.lower():
            return r"""# 🎯 【模擬輸出】PCFG 知識重點整理

這是因為您未設定 `GEMINI_API_KEY` 所產生的模擬結果。

## 1. 機率上下文無關文法 (PCFG)
* **定義**：在上下文無關文法 (CFG) 中，為每條語法規則賦予一個機率值。 [來源: nlp_chapter4.pdf 第20頁]
* **應用**：用來計算句子的最優語法分析樹，解決句法結構歧義。 [來源: nlp_chapter4.pdf 第20頁]

---
* 備註：模擬完成。如需真實 AI 整理，請在 `.env` 中設定 `GEMINI_API_KEY`。
"""
        else:
            # Dynamically extract slides from custom context
            lines = [l.strip() for l in context.split("\n")]
            slides_md = []
            
            main_title = "講義重點整理"
            for line in lines:
                if line:
                    main_title = line
                    break
                    
            slides_md.append(f"# 🎯 {main_title}\n")
            
            import re
            current_header = ""
            current_bullets = []
            
            for line in lines:
                if not line:
                    continue
                if re.match(r'^(第\d+頁|Page \d+)', line) or (line.endswith("？") or line.endswith("?")) or (len(line) < 25 and not line.startswith(("-", "*", "•"))):
                    if current_header:
                        slides_md.append(f"## {current_header}")
                        for b in current_bullets:
                            slides_md.append(f"* {b}")
                        slides_md.append("")
                    current_header = re.sub(r'^(第\d+頁|Page \d+)[:：\s]*', '', line).strip()
                    current_bullets = []
                elif line.startswith(("-", "*", "•", "1.", "2.", "3.")):
                    bullet_text = re.sub(r'^[\-\*\•\d\.]+\s*', '', line).strip()
                    current_bullets.append(bullet_text)
                else:
                    if len(line) > 8:
                        current_bullets.append(line)
                        
            # Flush last
            if current_header:
                slides_md.append(f"## {current_header}")
                for b in current_bullets:
                    slides_md.append(f"* {b}")
            else:
                slides_md.append("## 核心內容大綱")
                for line in lines[:10]:
                    if line and len(line) > 5 and line != main_title:
                        slides_md.append(f"* {line}")
                        
            slides_md.append("\n\n* 備註：此為離線離線分析結果。設定 `GEMINI_API_KEY` 後可啟用完整 AI 重點摘要！")
            return "\n".join(slides_md)
