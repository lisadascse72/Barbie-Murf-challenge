
from fastapi import FastAPI, UploadFile, File, HTTPException, Path as FastAPIPath, WebSocket, WebSocketDisconnect
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
import logging
import asyncio
import websockets
import json
import base64

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
if not MURF_API_KEY:
    logging.error("MURF_API_KEY not found in environment. Murf AI functions will fail.")

# --- Global Chat History Datastore ---
chat_history_store = {}
# --- End Global Chat History Datastore ---

# Load Gemini API key from env
GEMINI_API_KEY = os.getenv("VITE_GEMINI_API_KEY") # Note: frontend typically uses VITE_ prefix, backend usually not
if not GEMINI_API_KEY:
    logging.warning("VITE_GEMINI_API_KEY not found in environment. LLM functions may fail.")
else:
    genai.configure(api_key=GEMINI_API_KEY)


# --- Define Persona with "Stylist" Special Skill ---
BARBIE_PERSONA = {
    "role": "user",
    "parts": ["""From now on, you are a Barbie. You are always positive, enthusiastic, and ready for any adventure. You must always respond with a bubbly and encouraging tone, and use catchphrases like 'Hi, Barbie!' and 'You can be anything!'.

You have a special skill: you are a professional Barbie Stylist! When someone asks for fashion or styling advice, you must act as a stylist. Your advice should be bright, fun, and include suggestions for outfits, colors, and accessories that are perfect for any occasion. You can suggest things like:
- "A sparkly pink top with some fabulous flare jeans!"
- "A sunny yellow dress with a shimmering purse and heels!"
- "A bright blue jumpsuit with some glittery jewelry to make it pop!"
- "Remember, the perfect outfit always has a touch of sparkle!"
Always maintain your Barbie persona, even while giving detailed stylist advice. The goal is to make the user feel confident and stylish for their adventure!"""
]
}
# --- End Persona Definition ---


# --- Helper Function for Fallback Audio ---
FALLBACK_MESSAGE = "I'm having trouble connecting right now. Please try again later."
async def get_fallback_audio_url(text: str = FALLBACK_MESSAGE) -> str:
    if not MURF_API_KEY:
        logging.error("MURF_API_KEY is missing for fallback audio generation.")
        return ""

    payload = {
        "text": text,
        # Using a stable, known female voice from Murf's library to avoid connection issues.
        "voiceId": "en-US-teresa",
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
                timeout=10
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
        "user_transcript": user_transcript,
        "llm_response_text": FALLBACK_MESSAGE,
        "llm_response_audio_url": fallback_audio_url,
        "message": f"❌ Error: {detail}",
        "status_code": status_code
    }
    return response_content

# --- WebSocket Endpoint for Streaming Chat ---
@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logging.info(f"WebSocket connected for session: {session_id}")

    try:
        while True:
            message = await websocket.receive_text()
            logging.info(f"Received WebSocket message: {message} for session {session_id}")
            
            current_chat_history = chat_history_store.get(session_id, [])
            llm_response_text = ""
            for msg in reversed(current_chat_history):
                if msg["role"] == "model" and msg["parts"]:
                    llm_response_text = msg["parts"][0]
                    break
            
            if not llm_response_text:
                await websocket.send_json({"type": "error", "message": "No LLM response found to stream."})
                continue

            logging.info(f"Streaming LLM response: {llm_response_text[:50]}...")

            if not MURF_API_KEY:
                await websocket.send_json({"type": "error", "message": "Murf AI API key is missing."})
                continue

            murf_base_ws_url = "wss://api.murf.ai/v1/speech/stream-input"
            murf_ws_url_with_params = (
                f"{murf_base_ws_url}?api-key={MURF_API_KEY}&sample_rate=44100&channel_type=MONO&format=WAV"
            )

            try:
                # Connect to Murf AI WebSocket with the corrected URL and parameters
                async with websockets.connect(murf_ws_url_with_params) as murf_websocket:
                    logging.info("Connected to Murf AI WebSocket.")
                    
                    voice_config_msg = {
                        "voice_config": {
                            # CHANGE: Switched to a known stable female voice to ensure connection.
                            "voiceId": "en-US-teresa",
                            "style": "Conversational",
                            "rate": 0,
                            "pitch": 0,
                            "variation": 1
                        }
                    }
                    await murf_websocket.send(json.dumps(voice_config_msg))

                    text_msg = {
                        "text": llm_response_text,
                        "context_id": session_id,
                        "end": True
                    }
                    await murf_websocket.send(json.dumps(text_msg))

                    while True:
                        try:
                            murf_response = await murf_websocket.recv()
                            murf_data = json.loads(murf_response)

                            if "audio" in murf_data:
                                base64_audio = murf_data.get("audio")
                                if base64_audio:
                                    print(f"Received Base64 Audio Chunk: {base64_audio[:100]}...")
                                    await websocket.send_json({
                                        "type": "audio_chunk",
                                        "audio": base64_audio
                                    })
                            elif murf_data.get("final"):
                                logging.info("Murf AI finished streaming audio.")
                                await websocket.send_json({"type": "finished_audio"})
                                break
                            elif murf_data.get("type") == "error":
                                error_message = murf_data.get("message", "Unknown Murf error")
                                logging.error(f"Murf AI Streaming Error: {error_message}")
                                await websocket.send_json({"type": "error", "message": f"Murf Streaming Error: {error_message}"})
                                break
                        except websockets.exceptions.ConnectionClosedOK:
                            logging.warning("Murf AI WebSocket connection closed gracefully.")
                            break
                        except Exception as e:
                            logging.exception(f"Error receiving from Murf WS or processing: {e}")
                            await websocket.send_json({"type": "error", "message": f"Backend processing error: {e}"})
                            break
            except ConnectionRefusedError as e:
                logging.error(f"Murf AI WebSocket connection refused: {e}")
                await websocket.send_json({"type": "error", "message": "Failed to connect to Murf AI for streaming."})
            except Exception as e:
                logging.exception(f"Error establishing Murf WS connection: {e}")
                await websocket.send_json({"type": "error", "message": f"Murf WS connection failed: {e}"})

    except WebSocketDisconnect:
        logging.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logging.exception(f"WebSocket error for session {session_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "message": f"Server error: {e}"})
        except RuntimeError:
            pass

# This endpoint handles the initial audio upload, transcription, and LLM call.
# It then signals the client to open the WebSocket for streaming the LLM's response.
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

    # 3. Send combined history to Gemini LLM
    try:
        if not GEMINI_API_KEY:
            raise ValueError("Gemini API key is not configured.")
        
        # Add the persona to the chat history before starting the session
        persona_history = [BARBIE_PERSONA]
        combined_history = persona_history + current_chat_history

        model = genai.GenerativeModel("gemini-1.5-flash")
        chat_session = model.start_chat(history=combined_history)
        gemini_response = await chat_session.send_message_async(user_transcript)
        llm_response_text = gemini_response.text

        # Append LLM's response to the history
        current_chat_history.append({"role": "user", "parts": [user_transcript]})
        current_chat_history.append({"role": "model", "parts": [llm_response_text]})
        chat_history_store[session_id] = current_chat_history # Update the store

    except Exception as e:
        logging.exception("Gemini LLM request failed:")
        # Rollback user message if LLM fails
        if current_chat_history and current_chat_history[-1]["role"] == "user":
            current_chat_history.pop()
            chat_history_store[session_id] = current_chat_history
        return await create_error_response(500, f"LLM service failed: {e}", user_transcript)

    # Instead of direct Murf API call, now we'll signal the client to initiate WebSocket for streaming
    return {
        "user_transcript": user_transcript,
        "llm_response_text": llm_response_text, # Send this so UI can display it
        "message": "✅ Agent chat successful. Client should initiate WebSocket for audio streaming.",
        "session_id": session_id
    }

# Define the Pydantic model for text chat requests
class TextChatRequest(BaseModel):
    user_text: str

# This endpoint remains for text-based chat, but will also utilize the WebSocket for Murf streaming.
# We'll adjust its logic to return similar response as the audio chat and let the frontend handle WS.
@app.post("/agent/chat_text/{session_id}")
async def agent_chat_text(
    request: TextChatRequest, # MOVED THIS PARAMETER FIRST (no default)
    session_id: str = FastAPIPath(..., description="Unique ID for the chat session") # THIS REMAINS SECOND (with default)
):
    user_text_input = request.user_text.strip()

    if not user_text_input:
        return await create_error_response(400, "Text input is required.")
    
    # 1. Manage Chat History - Append user's message BEFORE LLM call
    current_chat_history = chat_history_store.get(session_id, [])

    # 2. Send combined history to Gemini LLM
    try:
        if not GEMINI_API_KEY:
            raise ValueError("Gemini API key is not configured.")
        
        # Add the persona to the chat history before starting the session
        persona_history = [BARBIE_PERSONA]
        combined_history = persona_history + current_chat_history

        model = genai.GenerativeModel("gemini-1.5-flash")
        chat_session = model.start_chat(history=combined_history)
        gemini_response = await chat_session.send_message_async(user_text_input)
        llm_response_text = gemini_response.text

        # Append LLM's response to the history
        current_chat_history.append({"role": "user", "parts": [user_text_input]})
        current_chat_history.append({"role": "model", "parts": [llm_response_text]})
        chat_history_store[session_id] = current_chat_history # Update the store

    except Exception as e:
        logging.exception("Gemini LLM request failed:")
        # Rollback user message if LLM fails
        if current_chat_history and current_chat_history[-1]["role"] == "user":
            current_chat_history.pop()
            chat_history_store[session_id] = current_chat_history
        return await create_error_response(500, f"LLM service failed: {e}", user_text_input)

    return {
        "user_text": user_text_input,
        "llm_response_text": llm_response_text,
        "message": "✅ Agent chat successful (text input). Client should initiate WebSocket for audio streaming.",
        "session_id": session_id
    }

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Root endpoint to serve the HTML file
@app.get("/")
async def get_index():
    with open(Path("static/index.html"), "r") as f:
        return f.read()