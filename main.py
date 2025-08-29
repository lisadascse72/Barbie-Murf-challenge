# main.py
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from fastapi.responses import FileResponse
import os
import httpx
import assemblyai as aai
import google.generativeai as genai
import logging
import json
import websockets

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for all origins, as required for a simple deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Key Management ---
MURF_API_KEY = os.getenv("MURF_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GEMINI_API_KEY = os.getenv("VITE_GEMINI_API_KEY")

if not MURF_API_KEY:
    logging.error("MURF_API_KEY not found in environment. Murf AI functions will fail.")
if not ASSEMBLYAI_API_KEY:
    logging.error("ASSEMBLYAI_API_KEY not found in environment. Transcription will fail.")
if not GEMINI_API_KEY:
    logging.warning("VITE_GEMINI_API_KEY not found in environment. LLM functions may fail.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# --- Global Chat History Datastore ---
chat_history_store = {}

# Define Barbie Persona
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

FALLBACK_MESSAGE = "I'm having trouble connecting right now. Please try again later."

async def create_error_response(status_code: int, detail: str, user_transcript: str = None) -> dict:
    logging.error(f"API Error - Status: {status_code}, Detail: {detail}")
    return {
        "user_transcript": user_transcript,
        "llm_response_text": FALLBACK_MESSAGE,
        "message": f"❌ Error: {detail}",
        "status_code": status_code
    }

# --- WebSocket Endpoint for Streaming Audio from Text ---
@app.websocket("/ws/audio_stream/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logging.info(f"WebSocket connected for session: {session_id}")

    try:
        current_chat_history = chat_history_store.get(session_id, [])
        llm_response_text = ""
        for msg in reversed(current_chat_history):
            if msg.get("role") == "model" and msg.get("parts") and isinstance(msg["parts"][0], str):
                llm_response_text = msg["parts"][0]
                break

        if not llm_response_text:
            await websocket.send_json({"type": "error", "message": "No LLM response found to stream."})
            return

        if not MURF_API_KEY:
            await websocket.send_json({"type": "error", "message": "Murf AI API key is missing."})
            return

        murf_base_ws_url = "wss://api.murf.ai/v1/speech/stream-input"
        murf_ws_url_with_params = (
            f"{murf_base_ws_url}?api-key={MURF_API_KEY}&sample_rate=44100&channel_type=MONO&format=WAV"
        )

        async with websockets.connect(murf_ws_url_with_params) as murf_websocket:
            logging.info("Connected to Murf AI WebSocket.")
            
            voice_config_msg = {
                "voice_config": {
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
        logging.exception(f"WebSocket processing error for session {session_id}: {e}")
        await websocket.send_json({"type": "error", "message": f"Server error: {e}"})

# --- Main Chat Endpoints ---

@app.post("/agent/chat/{session_id}")
async def agent_chat_audio(session_id: str, file: UploadFile):
    user_transcript = None
    
    if not ASSEMBLYAI_API_KEY:
        raise HTTPException(status_code=500, detail="Missing AssemblyAI API key. Please set it in .env.")

    try:
        audio_bytes = await file.read()
        aai.settings.api_key = ASSEMBLYAI_API_KEY
        transcriber = aai.Transcriber()
        transcript_obj = transcriber.transcribe(audio_bytes)
        user_transcript = transcript_obj.text

        if not user_transcript:
            return create_error_response(400, "Could not transcribe audio. Please speak more clearly.", user_transcript)
    except Exception as e:
        logging.exception("AssemblyAI transcription failed:")
        return create_error_response(500, f"Audio transcription service failed: {e}", user_transcript)

    current_chat_history = chat_history_store.get(session_id, [])

    try:
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API key is not configured.")
        
        persona_history = [BARBIE_PERSONA]
        combined_history = persona_history + current_chat_history

        model = genai.GenerativeModel("gemini-1.5-flash")
        chat_session = model.start_chat(history=combined_history)
        gemini_response = await chat_session.send_message_async(user_transcript)
        llm_response_text = gemini_response.text

        current_chat_history.append({"role": "user", "parts": [user_transcript]})
        current_chat_history.append({"role": "model", "parts": [llm_response_text]})
        chat_history_store[session_id] = current_chat_history

    except Exception as e:
        logging.exception("Gemini LLM request failed:")
        if current_chat_history and current_chat_history[-1]["role"] == "user":
            current_chat_history.pop()
            chat_history_store[session_id] = current_chat_history
        return create_error_response(500, f"LLM service failed: {e}", user_transcript)

    return {
        "user_transcript": user_transcript,
        "llm_response_text": llm_response_text,
        "message": "✅ Agent chat successful. Client should initiate WebSocket for audio streaming.",
        "session_id": session_id
    }

class TextChatRequest(BaseModel):
    user_text: str

@app.post("/agent/chat_text/{session_id}")
async def agent_chat_text(request: TextChatRequest, session_id: str):
    user_text_input = request.user_text.strip()
    if not user_text_input:
        return create_error_response(400, "Text input is required.")
    
    current_chat_history = chat_history_store.get(session_id, [])

    try:
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API key is not configured.")
        
        persona_history = [BARBIE_PERSONA]
        combined_history = persona_history + current_chat_history

        model = genai.GenerativeModel("gemini-1.5-flash")
        chat_session = model.start_chat(history=combined_history)
        gemini_response = await chat_session.send_message_async(user_text_input)
        llm_response_text = gemini_response.text

        current_chat_history.append({"role": "user", "parts": [user_text_input]})
        current_chat_history.append({"role": "model", "parts": [llm_response_text]})
        chat_history_store[session_id] = current_chat_history

    except Exception as e:
        logging.exception("Gemini LLM request failed:")
        if current_chat_history and current_chat_history[-1]["role"] == "user":
            current_chat_history.pop()
            chat_history_store[session_id] = current_chat_history
        return create_error_response(500, f"LLM service failed: {e}", user_text_input)

    return {
        "user_text": user_text_input,
        "llm_response_text": llm_response_text,
        "message": "✅ Agent chat successful (text input). Client should initiate WebSocket for audio streaming.",
        "session_id": session_id
    }

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

@app.get("/", response_class=FileResponse)
async def get_index():
    return Path("static/index.html")