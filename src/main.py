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

    def _parse_student_option(self, text: str) -> str | None:
        """
        解析學生的輸入是否為單一的選擇題選項（如 A, B, C, D）。
        支援各種彈性格式，包括前後空格、括號、標點與常見的答題描述。
        """
        import re
        if not text:
            return None
            
        text_clean = text.strip()
        
        # 1. 只有單個字母（前後可能有空白、括號或標點符號，例如 " B ", "b.", "(A)", "C、", "d)"）
        single_letter_match = re.search(r'^\s*[\(\[\{【]?\s*([A-Da-d])\s*[\)\]\}】\.\、]?\s*$', text_clean)
        if single_letter_match:
            return single_letter_match.group(1).upper()
            
        # 2. 包含明確的選取關鍵字（如 "我選B", "選 B", "答案是B", "選項是B", "選A項"）
        pattern_after = re.search(
            r'(?:選|答案是|寫|答|選擇|選項為|應該是|答案|是|為)\s*[:：\-—、\s,\"\'「『\(（]?\s*([A-Da-d])\s*[:：\-—、\s,\"\'」』\)）]?', 
            text_clean
        )
        if pattern_after:
            return pattern_after.group(1).upper()

        pattern_before = re.search(
            r'[\"\'「『\(（]?\s*([A-Da-d])\s*[\"\'」』\)）]?\s*(?:選項|是答案|對|才對|比較對|這選項)',
            text_clean
        )
        if pattern_before:
            return pattern_before.group(1).upper()
            
        # 3. 如果字串非常短（長度小於等於 5）且包含 A, B, C, D 字母
        if len(text_clean) <= 5:
            short_match = re.search(r'([A-Da-d])', text_clean)
            if short_match:
                return short_match.group(1).upper()
                
        return None

    def run_command(self, user_input: str):
        """
        處理使用者輸入，進行意圖路由與對應工具調用。
        """
        user_input = user_input.strip()
        if not user_input:
            return
            
        print("\n" + "-"*40)
        tools.save_log("User", f"使用者輸入: '{user_input}'")

        # 優先檢查是否為進行中的測驗，且輸入可以被解析成選項
        detected_option = None
        if self.active_quiz:
            detected_option = self._parse_student_option(user_input)

        if detected_option:
            tools.save_log("System", f"偵測到測驗進行中，且輸入可識別為選項：'{detected_option}'")
            intent = "GRADING"
            confidence = 1.0
            params = {"student_answer": user_input}  # 傳遞原始作答，讓批改 Agent 也能保留學生原始輸入
            explanation = f"測驗進行中，且使用者輸入符合選項格式，系統自動識別選項為 {detected_option} 並路由至批改流程。"
            tools.save_log("IntentClassifier", f"分析結果 (自動路由): 意圖為 [{intent}] (信心度: {confidence:.2f})")
            print(f"💡 [意圖理由]：{explanation}")
        else:
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
        for idx, opt in enumerate(self.active_quiz.get("options", []), 1):
            print(f"  [{idx}] {opt}")
        print(f"[提示: 請直接輸入選項對應的數字 1-4，或輸入字母 A-D 作答！]")
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
    
    print("\n💡 系統已就緒！")
    
    while True:
        try:
            print("\n" + "="*50)
            print("  🌟 請選擇您想要執行的功能：")
            print("  1. 📚 整理講義重點 (Generate Summary)")
            print("  2. 📝 進行隨堂小測驗 (Take Quiz)")
            print("  3. 📅 生成個人化複習計畫 (Generate Study Plan)")
            print("  4. 💬 進行講義知識問答 (QA)")
            print("  5. 💾 查看當前學習狀態 (View State)")
            print("  6. 📂 查看系統日誌路徑 (View Logs)")
            print("  7. ❌ 退出系統 (Exit)")
            print("="*50)
            
            choice = input("👉 請輸入功能編號 (1-7): ").strip()
            if not choice:
                continue
                
            if choice == '1':
                print("\n[功能 - 整理講義重點]")
                topic = input("📝 請輸入要整理的主題 (例如 'TF-IDF'，直接 Enter 則使用預設): ").strip()
                topic = topic or "TF-IDF"
                system.handle_summary({"topic": topic})
                
            elif choice == '2':
                print("\n[功能 - 進行隨堂小測驗]")
                topic = input("📝 請輸入要測驗的主題 (例如 'TF-IDF'，直接 Enter 則使用預設): ").strip()
                topic = topic or "TF-IDF"
                count_str = input("🔢 請輸入要測驗的題數 (預設為 3): ").strip()
                count = 3
                if count_str:
                    try:
                        count = int(count_str)
                    except ValueError:
                        print("無效的數字，將採用預設題數 3 題。")
                
                system.handle_quiz({"topic": topic, "count": count})
                
                # 測驗出題後，直接在選單中引導作答
                if system.active_quiz:
                    print("\n" + "-"*40)
                    ans = input("✍️ 您的選擇 (請輸入數字 1-4 或字母 A-D，如 '2' / 'B'): ").strip()
                    if ans:
                        # 支援輸入數字 1-4 對應到 A-D
                        num_mapping = {"1": "A", "2": "B", "3": "C", "4": "D"}
                        mapped_ans = num_mapping.get(ans, ans)
                        # 進行批改
                        system.handle_grading({"student_answer": mapped_ans}, mapped_ans)
                    else:
                        print("⚠️ 未檢測到輸入，取消本次作答。")
                        system.active_quiz = None
                
            elif choice == '3':
                print("\n[功能 - 生成個人化複習計畫]")
                exam_date = input("📅 請輸入預計考試日期 (格式如 2026-06-15，直接 Enter 則使用預設): ").strip()
                exam_date = exam_date or "2026-06-15"
                system.handle_study_plan({"exam_date": exam_date})
                
            elif choice == '4':
                print("\n[功能 - 講義知識問答]")
                question = input("💬 請輸入您想詢問講義的任何問題 (例如 '什麼是 TF-IDF？'): ").strip()
                if question:
                    system.handle_qa(question, {"topic": question})
                else:
                    print("⚠️ 問題不能為空！")
                    
            elif choice == '5':
                system.show_state()
                
            elif choice == '6':
                print(f"\n📂 本地日誌檔路徑: {tools.get_log_path()}\n")
                
            elif choice == '7':
                print("👋 系統關閉，學習加油！")
                break
            else:
                print("❌ 無效的選擇，請輸入 1 至 7 的數字。")
                
        except KeyboardInterrupt:
            print("\n👋 系統關閉，學習加油！")
            break
        except Exception as e:
            print(f"💥 發生系統錯誤: {e}")

if __name__ == "__main__":
    main()
