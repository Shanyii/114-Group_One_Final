import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure the project root is in the python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.agents.router import IntentClassifier
import src.tools as tools

class StudyAgentSystem:
    def __init__(self):
        print("="*60)
        print("🤖 課堂講義學習與複習規劃 Agent 系統 - 本地測試端 (已整合 Tool Calling)")
        print("="*60)
        
        # 1. 呼叫工具: save_log
        tools.save_log("System", "系統啟動中...")

        # 2. 初始化核心意圖判斷 Router
        self.router = IntentClassifier()

        # 暫存目前發布的測驗題目，供批改時對照
        self.active_quiz = None 
        
        tools.save_log("System", "核心 Agent 初始化完成！")
        
        # 3. 呼叫工具: 預載入講義並建置知識庫
        self._pre_load_lectures()

    def _pre_load_lectures(self):
        tools.save_log("System", "開始預載入講義...")
        
        test_files = ["nlp_chapter3.pdf", "nlp_chapter4.pdf"]
        for file in test_files:
            # 呼叫工具: read_document
            tools.save_tool_log("read_document()", {"filepath": file}, "開始讀取...")
            text_content = tools.read_document(file)
            
            # 呼叫工具: retrieve_content 所在的知識庫匯入
            tools.save_tool_log("add_to_knowledge_base()", {"doc_name": file}, f"已讀取 {len(text_content)} 字元。")
            tools.add_to_knowledge_base(file, text_content)
            
            # 呼叫工具: mark_lecture_completed (更新學習狀態)
            tools.mark_lecture_completed(file)
            
        tools.save_log("System", "所有測試講義預載入完成，知識庫已就緒！")

    def run_command(self, user_input: str):
        """
        處理使用者輸入，進行意圖路由與對應工具調用。
        """
        user_input = user_input.strip()
        if not user_input:
            return
            
        print("\n" + "-"*40)
        tools.save_log("User", f"使用者輸入: '{user_input}'")

        # 呼叫 IntentClassifier 判斷意圖
        tools.save_log("IntentClassifier", "分析使用者意圖與參數中...")
        routing = self.router.classify_intent(user_input)
        
        intent = routing.get("intent")
        confidence = routing.get("confidence", 0.0)
        params = routing.get("parameters", {})
        explanation = routing.get("explanation", "")
        
        tools.save_log("IntentClassifier", f"分析結果: 意圖為 [{intent}] (信心度: {confidence:.2f})")
        print(f"💡 [意圖理由]：{explanation}")
        
        # 根據意圖路由到對應的工具處理
        if intent == "SUMMARY":
            self.handle_summary(params)
        elif intent == "QUIZ":
            self.handle_quiz(params)
        elif intent == "GRADING":
            self.handle_grading(params, user_input)
        elif intent == "QA":
            self.handle_qa(user_input, params)
        elif intent == "STUDY_PLAN":
            self.handle_study_plan(params)
        else:
            tools.save_log("System", "無法識別的意圖。")

    def handle_summary(self, params: dict):
        topic = params.get("topic") or "TF-IDF"
        tools.save_log("SummaryAgent", f"要求重點整理，主題: '{topic}'")
        
        # 呼叫工具: retrieve_content()
        tools.save_tool_log("retrieve_content()", {"query": topic}, "正在檢索講義內容...")
        context = tools.retrieve_content(topic)
        
        # 呼叫工具: generate_summary()
        tools.save_log("SummaryAgent", "開始產生重點摘要...")
        summary = tools.generate_summary(topic, context)
        
        print("\n=== 🎯 講義重點整理結果 ===")
        print(summary)
        print("==========================\n")
        tools.save_log("SummaryAgent", "重點摘要顯示完成。")

    def handle_quiz(self, params: dict):
        topic = params.get("topic") or "TF-IDF"
        count = params.get("count") or 3
        if isinstance(count, str):
            try:
                count = int(count)
            except ValueError:
                count = 3
                
        tools.save_log("QuizAgent", f"要求產生測驗，主題: '{topic}'，數量: {count} 題")
        
        # 呼叫工具: retrieve_content()
        tools.save_tool_log("retrieve_content()", {"query": topic}, "正在檢索講義出題範圍...")
        context = tools.retrieve_content(topic)
        
        # 呼叫工具: generate_quiz()
        tools.save_log("QuizAgent", "開始生成測驗題目...")
        quizzes = tools.generate_quiz(topic, count, context)
        
        if not quizzes:
            print("❌ 出題失敗，請確認知識庫是否有該主題講義。")
            tools.save_log("QuizAgent", "出題失敗。")
            return
            
        # 暫存第一題供使用者作答測試
        self.active_quiz = quizzes[0]
        
        print(f"\n=== 📝 隨堂小測驗 (已產生 {len(quizzes)} 題，以下為第 1 題) ===")
        print(f"題目: {self.active_quiz.get('question')}")
        print("選項:")
        for opt in self.active_quiz.get("options", []):
            print(f"  {opt}")
        print(f"[提示: 請直接輸入 '我選 A' 或類似內容來回答！]")
        print("==================================================\n")
        
        tools.save_log("QuizAgent", f"測驗題已呈現。已暫存第 1 題作答指標，待學生輸入。")

    def handle_grading(self, params: dict, user_input: str):
        if not self.active_quiz:
            print("⚠️ 目前沒有進行中的測驗，請先輸入「幫我出題」！")
            tools.save_log("GradingAgent", "無進行中的測驗，拒絕批改。")
            return
            
        student_ans = params.get("student_answer") or user_input
        tools.save_log("GradingAgent", f"收到作答: '{student_ans}'，開始比對正確答案: '{self.active_quiz.get('answer')}'")
        
        # 呼叫工具: grade_answer()
        result = tools.grade_answer(self.active_quiz, student_ans)
        
        print("\n=== 📝 批改反饋結果 ===")
        if result.get("is_correct"):
            print("🟢 答對了！")
        else:
            print("🔴 答錯了！")
        print(result.get("grading_feedback"))
        print("======================\n")
        
        # 呼叫工具: update_learning_state()
        tools.save_tool_log("update_learning_state()", result, "正在記錄學員弱點與進度...")
        tools.update_learning_state(result)
        
        # 清除暫存測驗
        self.active_quiz = None

    def handle_qa(self, user_input: str, params: dict):
        topic = params.get("topic") or user_input
        tools.save_log("RAGAgent", f"知識性問答，主題: '{topic}'")
        
        # 呼叫工具: retrieve_content()
        tools.save_tool_log("retrieve_content()", {"query": topic}, "正在檢索講義相關內容...")
        context = tools.retrieve_content(topic)
        
        # 這裡模擬一般 QA 回覆，如果有 API key 則呼叫大模型，沒有則印出檢索的 context
        # 使用 summary_agent 所代表的底層 client
        from src.tools.generation_tools import _summary_agent
        if _summary_agent.client:
            tools.save_log("QA", "呼叫 AI 解答問題中...")
            try:
                prompt = f"請根據以下講義內容，用繁體中文回答學生的問題。\n問題：{user_input}\n講義內容：\n{context}"
                response = _summary_agent.client.models.generate_content(
                    model=_summary_agent.model_name,
                    contents=prompt
                )
                print("\n=== 📖 講義解答 ===")
                print(response.text)
                print("==================\n")
            except Exception as e:
                print(f"API 呼叫失敗，以下為講義原文內容:\n{context}")
        else:
            print("\n=== 📖 講義原文段落檢索 (未設定 API Key) ===")
            print(context)
            print("==========================================\n")
            
        tools.save_log("QA", "問答回覆完成。")

    def handle_study_plan(self, params: dict):
        exam_date = params.get("exam_date") or "2026-06-15"
        tools.save_log("StudyPlannerAgent", f"要求產生考前複習計畫，預計考試日: {exam_date}")
        
        # 呼叫工具: 讀取 Memory 狀態 (get_weak_topics, get_completed_lectures)
        weak_topics = tools.get_weak_topics()
        completed_lectures = tools.get_completed_lectures()
        
        tools.save_tool_log("get_learning_state()", {}, f"當前弱點: {weak_topics}")
        
        # 呼叫工具: generate_study_plan()
        tools.save_log("StudyPlannerAgent", "開始編排個人化考前複習計畫...")
        plan = tools.generate_study_plan(weak_topics, completed_lectures, exam_date)
        
        print("\n=== 📅 個人化複習規劃表 ===")
        print(plan)
        print("==========================\n")
        tools.save_log("StudyPlannerAgent", "讀書計畫顯示完成。")

    def show_state(self):
        print("\n=== 💾 目前學生學習狀態 (student_state.json) ===")
        student_state = tools.get_student_state()
        for k, v in student_state.items():
            print(f"{k}: {v}")
        print("===============================================\n")

def main():
    # 載入 .env
    load_dotenv()
    
    # 建立系統
    system = StudyAgentSystem()
    
    print("\n💡 系統已就緒！您可以輸入任何想要執行的動作。")
    print("  * 輸入「幫我整理 TF-IDF 重點」來測試摘要。")
    print("  * 輸入「出 2 題 TF-IDF」來測試出題，出題後輸入「我選 B」進行答題。")
    print("  * 輸入「產生讀書計畫」來規劃複習。")
    print("  * 輸入 'state' 查看當前弱點檔案、'logs' 查看日誌檔路徑。")
    print("  * 輸入 'exit' 退出系統。\n")
    
    while True:
        try:
            user_input = input("靖恩您的指令 >> ").strip()
            if not user_input:
                continue
                
            if user_input.lower() == 'exit':
                print("👋 系統關閉，學習加油！")
                break
            elif user_input.lower() == 'state':
                system.show_state()
            elif user_input.lower() == 'logs':
                print(f"\n📂 本地日誌檔路徑: {tools.get_log_path()}\n")
            else:
                system.run_command(user_input)
        except KeyboardInterrupt:
            print("\n👋 系統關閉，學習加油！")
            break
        except Exception as e:
            print(f"💥 發生系統錯誤: {e}")

if __name__ == "__main__":
    main()
