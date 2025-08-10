from fastapi import FastAPI, UploadFile, File, HTTPException
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
    allow_origins=["*"],  # Change this for production security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Your Murf API key from .env
MURF_API_KEY = os.getenv("MURF_API_KEY")

# Model for TTS request
class TTSRequest(BaseModel):
    text: str
    voiceId: str = "en-US-terrell"
    format: str = "MP3"

# ---------- TTS Generation Endpoint ----------
@app.post("/generate")
async def generate_tts(data: TTSRequest):
    if not MURF_API_KEY:
        raise HTTPException(status_code=500, detail="MURF_API_KEY not found in environment.")
    if not data.text.strip():
        raise HTTPException(status_code=400, detail="Text is required.")

    payload = {
        "text": data.text,
        "voiceId": data.voiceId,
        "format": data.format
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
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            return {
                "text_received": data.text,
                "audio_url": result.get("audioFile"),
                "note": "✅ Murf API call successful"
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- LLM Query Endpoint (Gemini) ----------
# Load Gemini API key from env
GEMINI_API_KEY = os.getenv("VITE_GEMINI_API_KEY") # Assuming VITE_GEMINI_API_KEY is used consistently
if not GEMINI_API_KEY:
    raise RuntimeError("VITE_GEMINI_API_KEY not found in environment.")

# Configure Gemini SDK
genai.configure(api_key=GEMINI_API_KEY)

@app.post("/llm/query_audio") # Changed endpoint name to avoid conflict with text-based if you want to keep it.
async def llm_query_audio(file: UploadFile = File(...)):
    # 1. Transcribe the audio using AssemblyAI
    ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
    if not ASSEMBLYAI_API_KEY:
        raise HTTPException(status_code=500, detail="Missing AssemblyAI API key.")

    try:
        audio_bytes = await file.read()
        aai.settings.api_key = ASSEMBLYAI_API_KEY
        transcriber = aai.Transcriber()
        transcript_obj = transcriber.transcribe(audio_bytes)
        transcribed_text = transcript_obj.text

        if not transcribed_text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio transcription failed: {str(e)}")

    # 2. Send transcribed text to Gemini
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        gemini_response = model.generate_content(transcribed_text)
        llm_response_text = gemini_response.text

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM request failed: {str(e)}")

    # 3. Send Gemini's response to Murf AI for TTS
    if not MURF_API_KEY:
        raise HTTPException(status_code=500, detail="MURF_API_KEY not found in environment for LLM response TTS.")

    murf_payload = {
        "text": llm_response_text,
        "voiceId": "en-US-terrell", # You can make this configurable if needed
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
                raise HTTPException(status_code=500, detail="Murf AI did not return an audio URL.")

            return {
                "original_transcript": transcribed_text,
                "llm_response_text": llm_response_text,
                "llm_response_audio_url": murf_audio_url,
                "message": "✅ LLM query and TTS successful"
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Murf AI TTS failed: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Murf AI TTS for LLM response failed: {str(e)}")


# ---------- Upload Audio Endpoint (Existing, kept for file saving if needed elsewhere) ----------
@app.post("/upload-audio/")
async def upload_audio(file: UploadFile = File(...)):
    try:
        # Save the uploaded file to /uploads folder
        file_location = UPLOAD_DIR / file.filename
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Get file size in KB
        file_size_kb = round(file_location.stat().st_size / 1024, 2)

        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": f"{file_size_kb} KB",
            "message": "✅ Upload successful"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# ---------- Serve uploaded files ----------
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ---------- Transcribe File Endpoint (Existing, but now LLM endpoint uses it internally) ----------
@app.post("/transcribe/file")
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        # Load API key
        ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
        if not ASSEMBLYAI_API_KEY:
            raise HTTPException(status_code=500, detail="Missing AssemblyAI API key.")

        # Read audio bytes
        audio_bytes = await file.read()

        # Use AssemblyAI SDK to transcribe
        aai.settings.api_key = ASSEMBLYAI_API_KEY
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_bytes)

        return {
            "transcript": transcript.text,
            "message": "✅ Transcription successful"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")