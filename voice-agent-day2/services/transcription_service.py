import os
import assemblyai as aai

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

async def transcribe_audio(audio_bytes: bytes) -> str:
    if not ASSEMBLYAI_API_KEY:
        raise ValueError("Missing AssemblyAI API key")

    aai.settings.api_key = ASSEMBLYAI_API_KEY
    transcriber = aai.Transcriber()
    transcript_obj = transcriber.transcribe(audio_bytes)
    return transcript_obj.text
