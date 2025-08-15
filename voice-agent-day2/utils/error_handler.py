import logging
from services.tts_service import generate_tts

FALLBACK_MESSAGE = "I'm having trouble connecting right now. Please try again later."

async def create_error_response(status_code: int, detail: str, user_input: str = None) -> dict:
    logging.error(f"Error {status_code}: {detail}")
    try:
        fallback_audio_url = await generate_tts(FALLBACK_MESSAGE)
    except:
        fallback_audio_url = ""

    return {
        "user_input": user_input,
        "llm_response_text": FALLBACK_MESSAGE,
        "llm_response_audio_url": fallback_audio_url,
        "message": f"❌ {detail}",
        "status_code": status_code
    }
