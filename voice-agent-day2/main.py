from fastapi import FastAPI, UploadFile, File, HTTPException, Path as FastAPIPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
import os
import shutil
import httpx
import assemblyai as aai
import google.generativeai as genai
import logging # Import logging module

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Create uploads directory if not exists
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MURF_API_KEY = os.getenv("MURF_API_KEY")

class TTSRequest(BaseModel):
    text: str
    voiceId: str = "en-US-terrell"
    format: str = "MP3"

# --- Global Chat History Datastore ---
chat_history_store = {}
# --- End Global Chat History Datastore ---

# Load Gemini API key from env
GEMINI_API_KEY = os.getenv("VITE_GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.warning("VITE_GEMINI_API_KEY not found in environment. LLM functions may fail.")
else:
    genai.configure(api_key=GEMINI_API_KEY)


# --- Helper Function for Fallback Audio ---
FALLBACK_MESSAGE = "I'm having trouble connecting right now. Please try again later."
# In a real app, you might pre-generate this audio and host it, or generate it on demand.
# For this task, we'll try to generate it using Murf AI if a failure occurs.
# If Murf also fails, the client will handle no audio URL being present.

async def get_fallback_audio_url(text: str = FALLBACK_MESSAGE) -> str:
    if not MURF_API_KEY:
        logging.error("MURF_API_KEY is missing for fallback audio generation.")
        return "" # No fallback audio if Murf key is missing

    payload = {
        "text": text,
        "voiceId": "en-US-terrell",
        "format": "MP3"
    }
    headers = {
        "api-key": MURF_API_KEY,
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.murf.ai/v1/speech/generate-with-key",
                json=payload,
                headers=headers,
                timeout=10 # Short timeout for fallback
            )
            response.raise_for_status()
            result = response.json()
            return result.get("audioFile", "")
    except Exception as e:
        logging.error(f"Failed to generate fallback audio via Murf AI: {e}")
        return ""

# --- Centralized Error Response Handler ---
async def create_error_response(status_code: int, detail: str, user_transcript: str = None) -> dict:
    logging.error(f"API Error - Status: {status_code}, Detail: {detail}")
    fallback_audio_url = await get_fallback_audio_url()
    
    response_content = {
        "user_transcript": user_transcript, # Keep original transcript if available
        "llm_response_text": FALLBACK_MESSAGE,
        "llm_response_audio_url": fallback_audio_url,
        "message": f"❌ Error: {detail}",
        "status_code": status_code
    }
    return response_content


# ---------- Chat History Endpoint: POST /agent/chat/{session_id} (for AUDIO input) ----------
@app.post("/agent/chat/{session_id}")
async def agent_chat_audio(
    session_id: str = FastAPIPath(..., description="Unique ID for the chat session"),
    file: UploadFile = File(...)
):
    user_transcript = None
    
    # 1. Transcribe the user's audio input using AssemblyAI
    ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
    if not ASSEMBLYAI_API_KEY:
        return await create_error_response(500, "Missing AssemblyAI API key. Please set it in .env.")

    try:
        audio_bytes = await file.read()
        aai.settings.api_key = ASSEMBLYAI_API_KEY
        transcriber = aai.Transcriber()
        transcript_obj = transcriber.transcribe(audio_bytes)
        user_transcript = transcript_obj.text

        if not user_transcript:
            return await create_error_response(400, "Could not transcribe audio. Please speak more clearly.", user_transcript)

    except Exception as e:
        logging.exception("AssemblyAI transcription failed:")
        return await create_error_response(500, f"Audio transcription service failed: {e}", user_transcript)

    # 2. Manage Chat History - Append user's message BEFORE LLM call
    current_chat_history = chat_history_store.get(session_id, [])
    current_chat_history.append({"role": "user", "parts": [user_transcript]})

    # 3. Send combined history to Gemini LLM
    try:
        if not GEMINI_API_KEY:
            raise ValueError("Gemini API key is not configured.")
        model = genai.GenerativeModel("gemini-1.5-flash")
        chat_session = model.start_chat(history=current_chat_history)
        gemini_response = await chat_session.send_message_async(user_transcript)
        llm_response_text = gemini_response.text

        # Append LLM's response to the history
        current_chat_history.append({"role": "model", "parts": [llm_response_text]})
        chat_history_store[session_id] = current_chat_history # Update the store

    except Exception as e:
        logging.exception("Gemini LLM request failed:")
        # If LLM call fails, remove the last user message to avoid sending unresponded message next time
        if current_chat_history and current_chat_history[-1]["role"] == "user":
            current_chat_history.pop()
            chat_history_store[session_id] = current_chat_history
        return await create_error_response(500, f"LLM service failed: {e}", user_transcript)


    # 4. Send Gemini's response to Murf AI for TTS
    if not MURF_API_KEY:
        return await create_error_response(500, "Missing Murf AI API key. Please set it in .env.", user_transcript)

    murf_payload = {
        "text": llm_response_text,
        "voiceId": "en-US-terrell",
        "format": "MP3"
    }
    murf_headers = {
        "api-key": MURF_API_KEY,
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            murf_res = await client.post(
                "https://api.murf.ai/v1/speech/generate-with-key",
                json=murf_payload,
                headers=murf_headers
            )
            murf_res.raise_for_status()
            murf_result = murf_res.json()
            murf_audio_url = murf_result.get("audioFile")
            if not murf_audio_url:
                raise ValueError("Murf AI did not return an audio URL.")

            return {
                "user_transcript": user_transcript,
                "llm_response_text": llm_response_text,
                "llm_response_audio_url": murf_audio_url,
                "message": "✅ Agent chat successful (audio input)",
                "session_id": session_id
            }
    except httpx.HTTPStatusError as e:
        logging.exception("Murf AI TTS failed with HTTP error:")
        return await create_error_response(e.response.status_code, f"Murf AI TTS failed: {e.response.text}", user_transcript)
    except Exception as e:
        logging.exception("Murf AI TTS failed unexpectedly:")
        return await create_error_response(500, f"Murf AI TTS service failed: {e}", user_transcript)


# ---------- Chat History Endpoint: POST /agent/chat_text/{session_id} (for TEXT input) ----------
class TextChatRequest(BaseModel):
    user_text: str

@app.post("/agent/chat_text/{session_id}")
async def agent_chat_text(
    session_id: str = FastAPIPath(..., description="Unique ID for the chat session"),
    request: TextChatRequest = None
):
    user_text_input = None # Initialize to None

    if not request or not request.user_text.strip():
        return await create_error_response(400, "Text input is required.")
    
    user_text_input = request.user_text.strip()

    # 1. Manage Chat History - Append user's message BEFORE LLM call
    current_chat_history = chat_history_store.get(session_id, [])
    current_chat_history.append({"role": "user", "parts": [user_text_input]})

    # 2. Send combined history to Gemini LLM
    try:
        if not GEMINI_API_KEY:
            raise ValueError("Gemini API key is not configured.")
        model = genai.GenerativeModel("gemini-1.5-flash")
        chat_session = model.start_chat(history=current_chat_history)
        gemini_response = await chat_session.send_message_async(user_text_input)
        llm_response_text = gemini_response.text

        # Append LLM's response to the history
        current_chat_history.append({"role": "model", "parts": [llm_response_text]})
        chat_history_store[session_id] = current_chat_history # Update the store

    except Exception as e:
        logging.exception("Gemini LLM request failed:")
        if current_chat_history and current_chat_history[-1]["role"] == "user":
            current_chat_history.pop()
            chat_history_store[session_id] = current_chat_history
        return await create_error_response(500, f"LLM service failed: {e}", user_text_input)

    # 3. Send Gemini's response to Murf AI for TTS
    if not MURF_API_KEY:
        return await create_error_response(500, "Missing Murf AI API key. Please set it in .env.", user_text_input)

    murf_payload = {
        "text": llm_response_text,
        "voiceId": "en-US-terrell",
        "format": "MP3"
    }
    murf_headers = {
        "api-key": MURF_API_KEY,
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            murf_res = await client.post(
                "https://api.murf.ai/v1/speech/generate-with-key",
                json=murf_payload,
                headers=murf_headers
            )
            murf_res.raise_for_status()
            murf_result = murf_res.json()
            murf_audio_url = murf_result.get("audioFile")
            if not murf_audio_url:
                raise ValueError("Murf AI did not return an audio URL.")

            return {
                "user_text": user_text_input,
                "llm_response_text": llm_response_text,
                "llm_response_audio_url": murf_audio_url,
                "message": "✅ Agent chat successful (text input)",
                "session_id": session_id
            }
    except httpx.HTTPStatusError as e:
        logging.exception("Murf AI TTS failed with HTTP error:")
        return await create_error_response(e.response.status_code, f"Murf AI TTS failed: {e.response.text}", user_text_input)
    except Exception as e:
        logging.exception("Murf AI TTS failed unexpectedly:")
        return await create_error_response(500, f"Murf AI TTS service failed: {e}", user_text_input)


# Serve uploaded files (needed for internal use, e.g., if Murf AI returns a local path)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

