from src.agents.log_agent import LogAgent

# Instantiate the LogAgent
_log_agent = LogAgent()

def save_log(agent_name: str, message: str) -> None:
    """
    紀錄 Agent 任務流程與工具呼叫。
    輸入：Agent 名稱 (str)、任務過程/Log 訊息 (str)
    輸出：無 (None)
    觸發時機：每次任務結束或關鍵步驟時
    """
    _log_agent.log_step(agent_name, message)

def save_tool_log(tool_name: str, inputs: dict, outputs: str) -> None:
    """
    額外工具呼叫日誌記錄。
    """
    _log_agent.log_tool_call(tool_name, inputs, outputs)

def get_log_path() -> str:
    """
    取得日誌檔案在本機的絕對路徑。
    """
    return str(_log_agent.log_path)
