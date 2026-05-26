import json
from pathlib import Path
from .base import BaseAgent

class MemoryAgent(BaseAgent):
    """
    MemoryAgent: Responsible for tracking the student's learning progress, weak topics, and quiz history.
    Saves state persistently to a local JSON file for testing and integration.
    """
    def __init__(self, state_filename: str = "student_state.json"):
        super().__init__()
        # Determine state path in the workspace root
        self.state_path = Path(__file__).resolve().parent.parent.parent / state_filename
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """
        Loads the student state from the JSON file. If it doesn't exist, returns a fresh state.
        """
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[MemoryAgent] 讀取狀態檔錯誤: {e}。建立新狀態。")
                
        # Default fresh state structure
        return {
            "user_id": "student_01",
            "weak_topics": {},         # Format: { "TF-IDF定義": 2, "PCFG概念": 1 }
            "completed_quizzes": 0,    # Total quizzes taken
            "correct_answers": 0,      # Total correct answers
            "completed_lectures": []   # List of filenames read (e.g. ["nlp_chapter3.pdf"])
        }

    def save_state(self):
        """
        Saves current memory state to the JSON file.
        """
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[MemoryAgent] 寫入狀態檔錯誤: {e}")

    def update_learning_state(self, grading_result: dict):
        """
        Updates student progress based on a GradingAgent output.
        """
        self.state["completed_quizzes"] += 1
        
        if grading_result.get("is_correct"):
            self.state["correct_answers"] += 1
        else:
            # Increment weak topic count if incorrect
            weakness = grading_result.get("concept_weakness")
            if weakness:
                current_count = self.state["weak_topics"].get(weakness, 0)
                self.state["weak_topics"][weakness] = current_count + 1
                
        self.save_state()
        print(f"[MemoryAgent] 狀態更新成功！目前弱點紀錄: {self.state['weak_topics']}")

    def mark_lecture_completed(self, filename: str):
        """
        Records that the student has read a slide document.
        """
        if filename not in self.state["completed_lectures"]:
            self.state["completed_lectures"].append(filename)
            self.save_state()
            print(f"[MemoryAgent] 講義讀取進度已記錄: {filename}")

    def get_weak_topics(self) -> dict:
        """
        Returns the weak topics dictionary.
        """
        return self.state.get("weak_topics", {})

    def get_completed_lectures(self) -> list:
        """
        Returns list of read lectures.
        """
        return self.state.get("completed_lectures", [])

    def analyze_weaknesses(self) -> str:
        """
        Analyzes the weak topics and outputs a summary string (弱點分析).
        """
        weak_topics = self.get_weak_topics()
        if not weak_topics:
            return "【弱點分析結果】恭喜！目前無任何答錯記錄，表現優異！"
            
        analysis = ["【弱點分析結果】"]
        # Sort by error count descending
        sorted_weak = sorted(weak_topics.items(), key=lambda x: x[1], reverse=True)
        for topic, count in sorted_weak:
            severity_str = "❗ 嚴重" if count >= 3 else "⚠️ 中度"
            analysis.append(f"- **{topic}**：答錯 {count} 次 ({severity_str})")
            
        return "\n".join(analysis)
