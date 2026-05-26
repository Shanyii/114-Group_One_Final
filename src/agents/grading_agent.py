import json
from pydantic import BaseModel, Field
from google.genai import types
from .base import BaseAgent

# Pydantic schemas for structured JSON output
class GradingResult(BaseModel):
    is_correct: bool = Field(description="學生答題是否正確，正確為 true，錯誤為 false")
    student_answer_raw: str = Field(description="學生的原始作答輸入")
    correct_answer: str = Field(description="本題的正確答案選項（A, B, C 或 D）")
    grading_feedback: str = Field(description="給學生的繁體中文評語、解析與盲點說明")
    concept_weakness: str | None = Field(None, description="若答錯，精確指出該題的概念弱點，如 'IDF定義'，若答對填 null")
    severity: str | None = Field(None, description="評估此盲點的嚴重程度: 'low' | 'medium' | 'high'，答對填 null")

class GradingAgent(BaseAgent):
    """
    GradingAgent: Evaluates student answers, provides pedagogical feedback, and diagnoses conceptual weaknesses.
    Input: Question, options, correct answer, explanation, source, and student's answer.
    Output: A dict matching GradingResult schema.
    """
    def __init__(self):
        super().__init__()
        try:
            self.template = self.load_prompt_template("grading_agent.txt")
        except FileNotFoundError:
            self.template = "請批改：\n題目: {{ QUESTION }}\n選項: {{ OPTIONS }}\n正確答案: {{ CORRECT_ANSWER }}\n學生答案: {{ STUDENT_ANSWER }}"

    def grade_answer(self, question_dict: dict, student_answer: str) -> dict:
        """
        Grades a student's answer to a given question.
        """
        # Format options as a list string
        options_str = "\n".join(question_dict.get("options", []))
        
        prompt = self.format_prompt(
            self.template,
            QUESTION=question_dict.get("question", ""),
            OPTIONS=options_str,
            CORRECT_ANSWER=question_dict.get("answer", ""),
            EXPLANATION=question_dict.get("explanation", ""),
            SOURCE=question_dict.get("source", ""),
            STUDENT_ANSWER=student_answer
        )

        if not self.client:
            print("[GradingAgent] 提示: 未偵測到 GEMINI_API_KEY，將啟用本地模擬批改。")
            return self._mock_grading(question_dict, student_answer)

        try:
            # Call Gemini with structured output configurations
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=GradingResult,
                    temperature=0.2 # Lower temperature for grading accuracy
                )
            )
            
            # Parse JSON result
            return json.loads(response.text)
            
        except Exception as e:
            print(f"[GradingAgent] API 呼叫或 JSON 解析失敗: {e}。啟用本地模擬批改。")
            return self._mock_grading(question_dict, student_answer)

    def _mock_grading(self, question_dict: dict, student_answer: str) -> dict:
        """
        Mock grading generated offline when API is unavailable.
        """
        correct_opt = question_dict.get("answer", "A")
        # Standardize student answer (extract first letter like 'A' or 'a')
        clean_student = student_answer.strip().upper()
        if len(clean_student) > 0 and clean_student[0] in ['A', 'B', 'C', 'D']:
            clean_student = clean_student[0]
            
        is_correct = (clean_student == correct_opt)
        
        # Craft feedback based on question
        topic = question_dict.get("topic", "講義內容")
        
        if is_correct:
            feedback = f"🎉 答對了！非常棒。這題考察的是「{topic}」。您選擇了 {correct_opt} 是完全正確的。請保持這樣的理解！"
            concept_weakness = None
            severity = None
        else:
            feedback = f"❌ 答錯囉。正確答案應該是 **{correct_opt}**。您的作答是 {student_answer}。\n\n解析提示：{question_dict.get('explanation', '')}"
            concept_weakness = f"{topic}定義" if "定義" in question_dict.get("question", "") else f"{topic}觀念"
            severity = "medium"
            
        return {
            "is_correct": is_correct,
            "student_answer_raw": student_answer,
            "correct_answer": correct_opt,
            "grading_feedback": feedback,
            "concept_weakness": concept_weakness,
            "severity": severity
        }
