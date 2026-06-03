from src.agents.memory_agent import MemoryAgent
from src.agents.study_planner_agent import StudyPlannerAgent

# Instantiate Memory and Planner agents
_memory_agent = MemoryAgent()
_planner_agent = StudyPlannerAgent()

def update_learning_state(grading_result: dict) -> None:
    """
    更新學生學習狀態與弱點。
    輸入：答題結果字典 (dict)
    輸出：無 (None)
    觸發時機：批改完成後
    """
    _memory_agent.update_learning_state(grading_result)

def generate_study_plan(weak_topics: dict, completed_lectures: list, exam_date: str) -> str:
    """
    產生個人化複習計畫。
    輸入：弱點紀錄字典 (dict)、已讀講義清單 (list)、考試時間 (str)
    輸出：讀書計畫 Markdown 內容 (str)
    觸發時機：使用者要求複習規劃時
    """
    return _planner_agent.generate_study_plan(weak_topics, completed_lectures, exam_date)

# Helper functions for state accessing
def get_weak_topics() -> dict:
    """
    取得目前的學員弱點資料。
    """
    return _memory_agent.get_weak_topics()

def get_completed_lectures() -> list:
    """
    取得已完成讀取的講義清單。
    """
    return _memory_agent.get_completed_lectures()

def mark_lecture_completed(filename: str) -> None:
    """
    標記某份講義已讀取完成。
    """
    _memory_agent.mark_lecture_completed(filename)

def get_student_state() -> dict:
    """
    取得學生整體的學習狀態字典。
    """
    return _memory_agent.state
