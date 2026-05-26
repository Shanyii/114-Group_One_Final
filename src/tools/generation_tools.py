from src.agents.summary_agent import SummaryAgent
from src.agents.quiz_agent import QuizAgent
from src.agents.grading_agent import GradingAgent

# Instantiate the agents
_summary_agent = SummaryAgent()
_quiz_agent = QuizAgent()
_grading_agent = GradingAgent()

def generate_summary(query: str, rag_context: str) -> str:
    """
    產生章節重點整理。
    輸入：主題/查詢 (str), 講義段落 (str)
    輸出：重點摘要 Markdown (str)
    觸發時機：使用者要求整理重點時
    """
    return _summary_agent.generate_summary(query, rag_context)

def generate_quiz(topic: str, count: int, rag_context: str) -> list[dict]:
    """
    根據講義內容產生測驗題。
    輸入：主題 (str)、題數 (int) [預設為單選題型]、講義內容 (str)
    輸出：題目與答案清單 (list of dicts)
    觸發時機：使用者要求練習時
    """
    return _quiz_agent.generate_quiz(topic, count, rag_context)

def grade_answer(question_dict: dict, student_answer: str) -> dict:
    """
    批改學生答案並提供解析。
    輸入：題目字典 (dict)、學生答案 (str)
    輸出：對錯判斷與解釋的 JSON/Dict (dict)
    觸發時機：學生提交答案時
    """
    return _grading_agent.grade_answer(question_dict, student_answer)
