from datetime import datetime
from .base import BaseAgent

class StudyPlannerAgent(BaseAgent):
    """
    StudyPlannerAgent: Responsible for generating personalized study/review schedules based on weak topics and exam dates.
    Input: Weak topics dict, completed lectures list, and exam date string.
    Output: Markdown structured study plan.
    """
    def __init__(self):
        super().__init__()
        try:
            self.template = self.load_prompt_template("study_planner_agent.txt")
        except FileNotFoundError:
            self.template = "請產生讀書計畫：\n弱點: {{ WEAK_TOPICS }}\n考試日期: {{ EXAM_DATE }}\n剩餘天數: {{ DAYS_REMAINING }}\n講義: {{ COMPLETED_LECTURES }}"

    def generate_study_plan(self, weak_topics: dict, completed_lectures: list, exam_date_str: str) -> str:
        """
        Generates a study plan using Gemini API, or falls back to local mock plan.
        """
        # Calculate days remaining until exam
        days_remaining = 3  # Default fallback
        try:
            exam_date = datetime.strptime(exam_date_str, "%Y-%m-%d")
            today = datetime.now()
            delta = exam_date - today
            days_remaining = max(0, delta.days)
        except Exception:
            # Handle non-standard date format
            pass
            
        # Format input variables
        weak_topics_text = ""
        if not weak_topics:
            weak_topics_text = "無（目前答對所有題目）"
        else:
            weak_topics_text = "\n".join([f"- {k}: 答錯 {v} 次" for k, v in weak_topics.items()])
            
        lectures_text = ", ".join(completed_lectures) if completed_lectures else "尚未閱讀任何講義"

        prompt = self.format_prompt(
            self.template,
            WEAK_TOPICS=weak_topics_text,
            EXAM_DATE=exam_date_str,
            DAYS_REMAINING=days_remaining,
            COMPLETED_LECTURES=lectures_text
        )

        if not self.client:
            print("[StudyPlannerAgent] 提示: 未偵測到 GEMINI_API_KEY，將啟用本地模擬生成複習計畫。")
            return self._mock_study_plan(weak_topics, completed_lectures, exam_date_str, days_remaining)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"[StudyPlannerAgent] API 呼叫失敗: {e}。啟用本地模擬生成複習計畫。")
            return self._mock_study_plan(weak_topics, completed_lectures, exam_date_str, days_remaining)

    def _mock_study_plan(self, weak_topics: dict, completed_lectures: list, exam_date: str, days_remaining: int) -> str:
        """
        Mock study plan generated offline when API is unavailable.
        """
        topic_analysis = []
        if not weak_topics:
            topic_analysis.append("1. **觀念穩固**：目前您沒有答錯的概念，建議保持日常練習即可！")
        else:
            for i, (topic, count) in enumerate(weak_topics.items(), 1):
                topic_analysis.append(f"{i}. **{topic}**（答錯 {count} 次）：建議重新閱讀相關講義。")
                
        topic_analysis_str = "\n".join(topic_analysis)

        return f"""# 🎯 【模擬輸出】個人化考前複習計畫

這是因為您未設定 `GEMINI_API_KEY` 所產生的模擬計畫。設定 Key 後將能獲得 AI 根據您的弱點量身定制的複習時間表！

## 🔍 您的學習現狀分析
根據您的答題紀錄，我們為您診斷出以下需要加強的觀念：
{topic_analysis_str}

---

## 📅 複習時間表 (距離考試剩餘 {days_remaining} 天，考試日期: {exam_date})

| 階段 / 日期 | 複習重點 | 具體行動建議 | 預估時間 |
| ---------- | -------- | ------------ | -------- |
| 第一階段 (Day 1) | 弱點突破 | 針對答錯次數最多的主題，複習對應講義段落並在系統重新測試。 | 60 分鐘 |
| 第二階段 (Day 2) | 概念對比與混合測試 | 比較相似或混淆的公式概念，做 5 題測驗以驗證理解。 | 45 分鐘 |
| 第三階段 (考前) | 總體複習與模擬 | 瀏覽系統整理的重點摘要，保持平常心。 | 30 分鐘 |

---

## 💡 學習教練的溫馨小建議
* 複習時請多注意公式的細節，特別是分母和極端值的變化。
* 只要把這幾個弱點補齊，您就準備好迎接考試了！加油！
"""
