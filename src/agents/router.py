import json
from pydantic import BaseModel, Field
from google.genai import types
from .base import BaseAgent

class RouterParameters(BaseModel):
    topic: str | None = Field(None, description="意圖涉及的主題名稱（例如: 'TF-IDF'）")
    count: int | None = Field(None, description="要求產生的題數或章節數")
    question_id: int | None = Field(None, description="作答題目的 ID")
    student_answer: str | None = Field(None, description="學生的答案內容")
    exam_date: str | None = Field(None, description="預定的考試日期")

class RouterResult(BaseModel):
    intent: str = Field(description="分類結果，必須是 'SUMMARY' | 'QUIZ' | 'GRADING' | 'QA' | 'STUDY_PLAN' 之一")
    confidence: float = Field(description="分類信心度，介於 0.0 至 1.0 之間")
    parameters: RouterParameters = Field(description="從對話中提取出的參數資訊")
    explanation: str = Field(description="分類理由的簡短說明")

class IntentClassifier(BaseAgent):
    """
    IntentClassifier (Router): Analyzes user queries and routes them to the correct Agent.
    Input: User message string.
    Output: JSON structure containing intent classification and parameters.
    """
    def __init__(self):
        super().__init__()
        try:
            self.template = self.load_prompt_template("intent_classifier.txt")
        except FileNotFoundError:
            self.template = "請分類意圖：\n使用者輸入: {{ USER_INPUT }}"

    def classify_intent(self, user_input: str) -> dict:
        """
        Classifies the user input using Gemini API, or falls back to keyword matching if offline.
        """
        # If API client is not configured, use local keyword heuristics
        if not self.client:
            print("[IntentClassifier] 提示: 未偵測到 GEMINI_API_KEY，將啟用本地規則分類意圖。")
            return self._mock_classify(user_input)

        try:
            # We don't have custom parameters in the classifier prompt, but let's replace variables if any.
            # In the classifier template, we have no placeholders or we might have one if we format it.
            # Let's replace simple query if any.
            prompt = self.template + f"\n\n待分類輸入：{user_input}"
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RouterResult,
                    temperature=0.1
                )
            )
            
            return json.loads(response.text)
            
        except Exception as e:
            print(f"[IntentClassifier] API 呼叫或 JSON 解析失敗: {e}。啟用本地規則分類。")
            return self._mock_classify(user_input)

    def _mock_classify(self, text: str) -> dict:
        """
        Heuristic offline classifier based on simple keywords.
        """
        text_lower = text.lower()
        
        # Check if the input is an option selection (e.g. "B", "我選 B", "答案是 A", "選項 C")
        import re
        text_clean = text.strip()
        is_option = False
        ans = None
        
        # 1. Single letter option
        single_letter = re.search(r'^\s*[\(\[\{【]?\s*([A-Da-d])\s*[\)\]\}】\.\、]?\s*$', text_clean)
        if single_letter:
            is_option = True
            ans = single_letter.group(1).upper()
        else:
            # 2. Check with selection keywords
            pattern_after = re.search(
                r'(?:選|答案是|寫|答|選擇|選項為|應該是|答案|是|為)\s*[:：\-—、\s,\"\'「『\(（]?\s*([A-Da-d])\s*[:：\-—、\s,\"\'」』\)）]?', 
                text_clean
            )
            if pattern_after:
                is_option = True
                ans = pattern_after.group(1).upper()
            else:
                pattern_before = re.search(
                    r'[\"\'「『\(（]?\s*([A-Da-d])\s*[\"\'」』\)）]?\s*(?:選項|是答案|對|才對|比較對|這選項)',
                    text_clean
                )
                if pattern_before:
                    is_option = True
                    ans = pattern_before.group(1).upper()

        if is_option:
            return {
                "intent": "GRADING",
                "confidence": 0.95,
                "parameters": {
                    "topic": None,
                    "count": None,
                    "question_id": None,
                    "student_answer": ans or text,
                    "exam_date": None
                },
                "explanation": "輸入符合選擇題答案選項格式，判定為提交測驗答案。"
            }
            
        # Quiz check: e.g. "出題", "測驗", "練習", "出 2 題"
        if any(kw in text_lower for kw in ["出題", "測驗", "練習", "考我", "題目", "出", "題"]):
            # Try to guess count
            count = 3
            for i in range(1, 10):
                if str(i) in text:
                    count = i
                    break
            
            # Guess topic
            topic = "TF-IDF"
            if "pcfg" in text_lower:
                topic = "PCFG"
                
            return {
                "intent": "QUIZ",
                "confidence": 0.95,
                "parameters": {
                    "topic": topic,
                    "count": count,
                    "question_id": None,
                    "student_answer": None,
                    "exam_date": None
                },
                "explanation": "匹配到出題測驗關鍵字，判定為產生測驗題意圖。"
            }
            
        # Study plan check: e.g. "複習", "規劃", "計畫"
        if any(kw in text_lower for kw in ["複習", "規劃", "計畫", "讀書", "讀書計劃"]):
            return {
                "intent": "STUDY_PLAN",
                "confidence": 0.95,
                "parameters": {
                    "topic": None,
                    "count": None,
                    "question_id": None,
                    "student_answer": None,
                    "exam_date": "2026-06-15" # Mock exam date
                },
                "explanation": "匹配到複習與計畫關鍵字，判定為生成讀書計畫意圖。"
            }

        # Summary check: e.g. "摘要", "整理", "大綱", "投影片重點"
        if any(kw in text_lower for kw in ["摘要", "整理", "大綱", "重點"]):
            topic = "TF-IDF"
            if "pcfg" in text_lower:
                topic = "PCFG"
            return {
                "intent": "SUMMARY",
                "confidence": 0.90,
                "parameters": {
                    "topic": topic,
                    "count": None,
                    "question_id": None,
                    "student_answer": None,
                    "exam_date": None
                },
                "explanation": "匹配到整理摘要關鍵字，判定為摘要意圖。"
            }

        # Default QA
        topic = "TF-IDF"
        if "pcfg" in text_lower:
            topic = "PCFG"
        return {
            "intent": "QA",
            "confidence": 0.80,
            "parameters": {
                "topic": topic,
                "count": None,
                "question_id": None,
                "student_answer": None,
                "exam_date": None
            },
            "explanation": "未匹配到其他核心流程關鍵字，預設為知識性問答 (QA)。"
        }
