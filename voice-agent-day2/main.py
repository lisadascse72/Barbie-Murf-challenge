from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class TTSRequest(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {"message": "Welcome to Day 2 Voice Agent API. Use /docs to test."}

@app.post("/generate")
def generate_tts(data: TTSRequest):
    text = data.text

    if not text.strip():
        raise HTTPException(status_code=400, detail="Text is required.")

    # Simulated API call (since Murf's is private)
    fake_audio_url = f"https://example.com/audio/{text.replace(' ', '_')}.mp3"

    return {
        "text_received": text,
        "audio_url": fake_audio_url,
        "note": "Simulated Murf API response. No real API call made."
    }
