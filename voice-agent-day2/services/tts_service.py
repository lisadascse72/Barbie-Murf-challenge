import os
import httpx
import logging

MURF_API_KEY = os.getenv("MURF_API_KEY")

async def generate_tts(text: str, voice_id: str = "en-US-terrell", format_: str = "MP3"):
    if not MURF_API_KEY:
        raise ValueError("Missing Murf API key")

    payload = {
        "text": text,
        "voiceId": voice_id,
        "format": format_
    }
    headers = {
        "api-key": MURF_API_KEY,
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        res = await client.post("https://api.murf.ai/v1/speech/generate-with-key", json=payload, headers=headers)
        res.raise_for_status()
        result = res.json()
        audio_url = result.get("audioFile")
        if not audio_url:
            raise ValueError("No audio URL returned from Murf")
        return audio_url
