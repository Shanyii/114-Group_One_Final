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
        # Also print to terminal with nice blue styling (simulated)
        print(f"\033[94m[LOG] {log_entry}\033[0m")

    def log_tool_call(self, tool_name: str, inputs: dict, outputs: str):
        """
        Logs an agent tool call.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Truncate output if too long for cleaner logs
        truncated_out = (outputs[:100] + "...") if len(outputs) > 100 else outputs
        
        log_entry = f"[{timestamp}] [TOOL_CALL] 呼叫工具: {tool_name} | 參數: {inputs} | 結果摘要: {truncated_out}"
        self.run_logs.append(log_entry)
        self._write_to_file(log_entry)
        print(f"\033[92m[LOG] {log_entry}\033[0m")

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
