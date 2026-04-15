import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv(".env")
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env")
else:
    genai.configure(api_key=api_key)
    print(f"Checking models for key: {api_key[:8]}...")
    try:
        available_models = [m.name for m in genai.list_models()]
        print("\nAvailable models:")
        for m in available_models:
            print(f" - {m}")
        
        target = "models/gemini-1.5-flash"
        if target in available_models:
            print(f"\nSUCCESS: {target} is available.")
        else:
            print(f"\nFAILURE: {target} NOT found in list_models().")
            
    except Exception as e:
        print(f"\nError listing models: {e}")
