import os
import google.generativeai as genai

# Don't raise at import time — just read from env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def generate_llm_response(history, user_input):
    # Re-check inside the function to be safe
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("❌ Gemini API key is missing. Please check your .env file.")

    model = genai.GenerativeModel("gemini-1.5-flash")
    chat_session = model.start_chat(history=history)
    gemini_response = await chat_session.send_message_async(user_input)
    return gemini_response.text
