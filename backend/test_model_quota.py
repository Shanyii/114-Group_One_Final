import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

print(f"API Key: {api_key}")

models_to_test = [
    "models/gemini-2.0-flash",
    "models/gemini-1.5-flash",
    "models/gemini-2.5-flash"
]

for model_name in models_to_test:
    print(f"\n--- Testing {model_name} ---")
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say hello in one word")
        print(f"Success with {model_name}! Response: {response.text.strip()}")
    except Exception as e:
        print(f"Failed with {model_name}: {e}")
