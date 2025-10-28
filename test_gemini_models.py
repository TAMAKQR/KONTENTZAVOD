import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
    
    # Попробуем список доступных моделей
    models = genai.list_models()
    print("🔍 Доступные модели Gemini:")
    for m in models:
        print(f"  • {m.name}")
        if hasattr(m, 'supported_generation_methods'):
            if 'generateContent' in m.supported_generation_methods:
                print(f"    ✅ Поддерживает generateContent")
else:
    print("❌ GEMINI_API_KEY не найден")