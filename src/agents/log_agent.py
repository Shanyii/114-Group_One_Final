import os
from datetime import datetime
from pathlib import Path
from .base import BaseAgent

class LogAgent(BaseAgent):
    """
    LogAgent: Responsible for recording all Agent decision steps, actions, and tool calls.
    Input: Step details / action processes.
    Output: Structured Agent log.
    """
    def __init__(self, log_filename: str = "agent_run.log"):
        super().__init__()
        # Logs path at project workspace root
        self.log_path = Path(__file__).resolve().parent.parent.parent / log_filename
        self.run_logs = []
        
        # Initialize log file
        if not self.log_path.exists():
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write(f"=== Agent System Log Initialized at {datetime.now().isoformat()} ===\n")
                
        # Enable Windows ANSI console support
        if os.name == 'nt':
            os.system('')

    def _write_to_file(self, line: str):
        """
        Appends a line to the log file.
        """
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            print(f"[LogAgent] 寫入 Log 檔失敗: {e}")

    def log_step(self, agent_name: str, message: str):
        """
        Logs a standard agent execution step.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{agent_name}] {message}"
        self.run_logs.append(log_entry)
        self._write_to_file(log_entry)
        
        # Define agent friendly names, emojis, and roles
        agent_mapping = {
            "IntentClassifier": ("🧠 IntentClassifier", "意圖路由器"),
            "SummaryAgent": ("📝 SummaryAgent", "摘要精簡助理"),
            "QuizAgent": ("🎲 QuizAgent", "隨堂測驗出題官"),
            "GradingAgent": ("✍️ GradingAgent", "考卷批改診斷師"),
            "RAGAgent": ("🔍 RAGAgent", "知識庫搜尋引擎"),
            "StudyPlannerAgent": ("📅 StudyPlannerAgent", "學習計畫規劃師"),
            "System": ("⚙️ System", "系統核心"),
            "User": ("👤 User", "使用者輸入"),
            "QA": ("💬 QA Agent", "問答回覆模組"),
        }
        
        emoji_name, desc = agent_mapping.get(agent_name, (f"🤖 {agent_name}", "核心協同 Agent"))
        
        # Print a beautiful agent step trace box (Cyan style)
        print("\033[1;36m" + "┌" + "─" * 60 + "\033[0m")
        print(f"\033[1;36m│\033[0m \033[1;33m{emoji_name}\033[0m \033[90m({desc})\033[0m")
        print("\033[1;36m├" + "─" * 60 + "\033[0m")
        print(f"\033[1;36m│\033[0m ➔ \033[97m現階段任務:\033[0m {message}")
        print("\033[1;36m└" + "─" * 60 + "\033[0m")

    def log_tool_call(self, tool_name: str, inputs: dict, outputs: str):
        """
        Logs an agent tool call.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Format string representation of inputs/outputs for readability
        inputs_str = str(inputs)
        outputs_str = str(outputs)
        
        # Truncate output for logging
        truncated_out = (outputs_str[:150] + "...") if len(outputs_str) > 150 else outputs_str
        
        log_entry = f"[{timestamp}] [TOOL_CALL] 呼叫工具: {tool_name} | 參數: {inputs_str} | 結果摘要: {truncated_out}"
        self.run_logs.append(log_entry)
        self._write_to_file(log_entry)
        
        # Print a beautiful tool call status box (Green style)
        print("\033[1;32m" + "┌" + "─" * 60 + "\033[0m")
        print(f"\033[1;32m│\033[0m \033[1;92m🔧 呼叫工具 (Tool Calling):\033[0m \033[1;97m{tool_name}\033[0m")
        print("\033[1;32m├" + "─" * 60 + "\033[0m")
        print(f"\033[1;32m│\033[0m 📥 \033[97m輸入參數:\033[0m {inputs_str}")
        print(f"\033[1;32m│\033[0m 📤 \033[97m結果摘要:\033[0m {truncated_out}")
        print("\033[1;32m└" + "─" * 60 + "\033[0m")

    def get_run_logs(self) -> list:
        """
        Returns all logs in the current run.
        """
        return self.run_logs

    def clear_run_logs(self):
        """
        Clears the in-memory run logs.
        """
        self.run_logs = []
