import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env file
# Walk up directory tree to find .env file
root_dir = Path(__file__).resolve().parent.parent.parent
env_path = root_dir / ".env"
if not env_path.exists():
    env_path = root_dir / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

class BaseAgent:
    """
    Base class for all Agents. 
    Handles API client initialization and prompt loading.
    """
    def __init__(self):
        # Retrieve API key and check validity
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("WARNING: GEMINI_API_KEY is not set in environment or .env file.")
        
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Initialize Google GenAI client
        # In actual execution, if api_key is None, genai.Client() will raise an error or look for environment
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        
        # Base prompts directory path
        self.prompts_dir = root_dir / "prompts"

    def load_prompt_template(self, filename: str) -> str:
        """
        Loads a prompt template file from the prompts/ directory.
        """
        filepath = self.prompts_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Prompt template file not found: {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def format_prompt(self, template: str, **kwargs) -> str:
        """
        Replaces placeholder tokens like {{ VARIABLE }} in the template.
        """
        formatted = template
        for key, val in kwargs.items():
            formatted = formatted.replace(f"{{{{ {key} }}}}", str(val) if val is not None else "無")
        return formatted

    def get_client(self):
        """
        Returns the GenAI client, initializing it if not already done.
        """
        if not self.client:
            self.api_key = os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is required to initialize the GenAI Client.")
            self.client = genai.Client(api_key=self.api_key)
        return self.client
