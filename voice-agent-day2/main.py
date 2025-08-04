from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for frontend requests (adjust origin if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use ["http://127.0.0.1:5500"] for stricter setup
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get Murf API key from environment
MURF_API_KEY = os.getenv("MURF_API_KEY")

# Request body model
class TTSRequest(BaseModel):
    text: str
    voiceId: str = "en-US-terrell"
    format: str = "MP3"

# POST /generate endpoint
@app.post("/generate")
async def generate_tts(data: TTSRequest):
    if not MURF_API_KEY:
        raise HTTPException(status_code=500, detail="API key not found")
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
                "note": "✅ Real Murf API call successful"
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
