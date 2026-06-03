import json
from pydantic import BaseModel, Field
from google.genai import types
from .base import BaseAgent

# Pydantic schemas for structured JSON output
class QuizItem(BaseModel):
    id: int = Field(description="題目的唯一編號，從 1 開始遞增")
    topic: str = Field(description="本題目的核心主題考點 (例如: 'TF-IDF')")
    question: str = Field(description="題目描述，需清晰且只考講義內容")
    options: list[str] = Field(description="4個單選選項，以 A), B), C), D) 開頭")
    answer: str = Field(description="正確答案選項字元，必須是 'A'、'B'、'C' 或 'D' 中的一個")
    explanation: str = Field(description="對該題答案的詳細繁體中文解析")
    source: str = Field(description="題目考點在講義中的具體位置頁碼")

class QuizList(BaseModel):
    quizzes: list[QuizItem]

class QuizAgent(BaseAgent):
    """
    QuizAgent: Generates multiple-choice quiz questions based on the RAG context.
    Input: Topic name, question count, and the retrieved lecture context.
    Output: A list of dicts containing quiz questions, options, answers, and explanations.
    """
    def __init__(self):
        super().__init__()
        try:
            self.template = self.load_prompt_template("quiz_agent.txt")
        except FileNotFoundError:
            self.template = "請出題：\n主題: {{ TOPIC }}\n題數: {{ COUNT }}\n內容:\n{{ RAG_CONTEXT }}"

    def generate_quiz(self, topic: str, count: int, rag_context: str) -> list[dict]:
        """
        Generates quizzes by calling Gemini API with a structured output schema.
        Falls back to mock questions if the API key is missing or fails.
        """
        prompt = self.format_prompt(
            self.template,
            TOPIC=topic,
            COUNT=count,
            RAG_CONTEXT=rag_context
        )

        if not self.client:
            print("[QuizAgent] 提示: 未偵測到 GEMINI_API_KEY，將啟用本地模擬出題。")
            return self._mock_quiz(topic, count, rag_context)

        try:
            # Call Gemini with structured output configurations
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=QuizList,
                    temperature=0.7
                )
            )
            
            # Parse JSON result
            data = json.loads(response.text)
            return data.get("quizzes", [])
            
        except Exception as e:
            print(f"[QuizAgent] API 呼叫或 JSON 解析失敗: {e}。啟用本地模擬出題。")
            return self._mock_quiz(topic, count, rag_context)

    def _mock_quiz(self, topic: str, count: int, context: str = "") -> list[dict]:
        """
        Mock questions generated offline when API is unavailable.
        """
        mock_data = []
        if "tf-idf" in topic.lower() or "tfidf" in topic.lower():
            mock_data = [
                {
                    "id": 1,
                    "topic": "TF-IDF",
                    "question": "在 TF-IDF 演算法中，如果一個單字在所有文件中都出現（例如：的、是），它的 IDF 值通常會如何變化？",
                    "options": [
                        "A) 會變得非常高，表示該字最重要",
                        "B) 會趨近於 0，因為它的區別力極低",
                        "C) 保持不變，與出現頻率無關",
                        "D) 會變成負值，干擾計算"
                    ],
                    "answer": "B",
                    "explanation": "根據 IDF 公式，分母是包含該詞的文件數。若一個詞在所有文件中都出現，IDF 分子分母接近，log(1) = 0，IDF 值趨近於 0，表示該單字區別不同文件的能力極低。",
                    "source": "nlp_chapter3.pdf 第12頁"
                },
                {
                    "id": 2,
                    "topic": "TF-IDF",
                    "question": "詞頻 (TF) 的計算公式中，分母代表的意義是什麼？",
                    "options": [
                        "A) 整份文件庫中所有單字的總數",
                        "B) 該詞彙在所有文件中出現的次數總和",
                        "C) 該單一文件中所有詞彙的出現次數總和",
                        "D) 所有文件的個數 N"
                    ],
                    "answer": "C",
                    "explanation": "TF 計算的是單一詞彙在某文件中的頻率。為了標準化，公式分母為該文件中所有詞彙的出現次數總和，避免長文件對詞頻造成偏誤。",
                    "source": "nlp_chapter3.pdf 第5頁"
                },
                {
                    "id": 3,
                    "topic": "TF-IDF",
                    "question": "如何計算一個字詞在某文件中的 TF-IDF 權重？",
                    "options": [
                        "A) 將 TF 值除以 IDF 值",
                        "B) 將 TF 值與 IDF 值相加",
                        "C) 將 TF 值與 IDF 值相乘",
                        "D) 將 IDF 值除以 TF 值"
                    ],
                    "answer": "C",
                    "explanation": "TF-IDF 權重是透過將詞頻 (TF) 與逆文件頻率 (IDF) 相乘得到：TF-IDF = TF * IDF。這同時考慮了單字在單一文件中的重要性與在文件庫中的代表性。",
                    "source": "nlp_chapter3.pdf 第15頁"
                }
            ]
        elif "pcfg" in topic.lower():
            mock_data = [
                {
                    "id": 1,
                    "topic": "PCFG",
                    "question": "在 PCFG 中，對於同一個左側非終端符號 (Non-terminal) 的所有規則，其機率之和必須滿足什麼條件？",
                    "options": [
                        "A) 大於 1",
                        "B) 等於 0",
                        "C) 等於 1",
                        "D) 小於 0.5"
                    ],
                    "answer": "C",
                    "explanation": "PCFG 的定義規定，對於任何一個左側非終端符號（例如 NP），其所有擴展規則（如 NP -> Det N, NP -> Pronoun）的機率總和必須等於 1.0。",
                    "source": "nlp_chapter4.pdf 第20頁"
                },
                {
                    "id": 2,
                    "topic": "PCFG",
                    "question": "PCFG 比起傳統上下文無關文法 (CFG)，最主要的多出的優勢是什麼？",
                    "options": [
                        "A) 可以處理更長的句子",
                        "B) 能為歧義句子的不同語法樹計算機率，挑選出最合理的結構",
                        "C) 不再需要定義非終端符號",
                        "D) 執行速度絕對快 10 倍"
                    ],
                    "answer": "B",
                    "explanation": "PCFG 的核心優勢在於能為句子的不同解析樹計算機率。面對歧義句（例如同個句子有兩種結構）時，PCFG 可以找出機率最高的樹作為最合適的語法解析結果。",
                    "source": "nlp_chapter4.pdf 第20頁"
                }
            ]
        else:
            mock_data = [
                {
                    "id": 1,
                    "topic": "講義重點",
                    "question": "根據您上傳的講義內容，以下關於課程主題的敘述何者最為正確？",
                    "options": [
                        "A) 講義主要是關於所上傳的學科或主題概念說明",
                        "B) 講義主題與任何自然語言處理或課程核心無關",
                        "C) 講義僅包含隨機亂碼，沒有任何實質學習觀念",
                        "D) 以上皆非"
                    ],
                    "answer": "A",
                    "explanation": "此為基於上傳講義的觀念檢索。您可以在設定 API Key 後獲得 AI 生成的精準客製化考題。",
                    "source": "上傳講義內容"
                }
            ]
            
            if context:
                import re
                lines = [l.strip() for l in context.split("\n") if len(l.strip()) > 12 and not l.startswith(("#", "第"))]
                for line in lines:
                    if "定義" in line or "是指" in line or "為" in line or "：" in line:
                        clean_line = re.sub(r'^[\-\*\•\d\.]+\s*', '', line).strip()
                        mock_data.append({
                            "id": 2,
                            "topic": "核心名詞理解",
                            "question": f"講義提及：「{clean_line[:60]}...」，這代表了什麼重要觀念？",
                            "options": [
                                "A) 這說明了講義中提及的關鍵要素及其實際定義",
                                "B) 這是一個不具任何參考價值的部分",
                                "C) 這是有關排程或二元樹的無關公式",
                                "D) 這只是一個系統產生的無用佔位符"
                            ],
                            "answer": "A",
                            "explanation": f"講義原文中明確指出：「{clean_line}」",
                            "source": "上傳講義內容"
                        })
                        break
            
        # Return only the requested number of questions
        return mock_data[:count]
