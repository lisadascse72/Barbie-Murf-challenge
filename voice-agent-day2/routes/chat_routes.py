from fastapi import APIRouter, File, UploadFile, Path
from models.chat_models import TextChatRequest
from services.transcription_service import transcribe_audio
from services.llm_service import generate_llm_response
from services.tts_service import generate_tts
from utils.error_handler import create_error_response

router = APIRouter()
chat_history_store = {}

@router.post("/agent/chat/{session_id}")
async def chat_audio(session_id: str = Path(...), file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        user_text = await transcribe_audio(audio_bytes)
        if not user_text:
            return await create_error_response(400, "No transcription found")

        history = chat_history_store.get(session_id, [])
        history.append({"role": "user", "parts": [user_text]})
        llm_text = await generate_llm_response(history, user_text)
        history.append({"role": "model", "parts": [llm_text]})
        chat_history_store[session_id] = history

        audio_url = await generate_tts(llm_text)
        return {"user_transcript": user_text, "llm_response_text": llm_text, "llm_response_audio_url": audio_url}

    except Exception as e:
        return await create_error_response(500, str(e))

@router.post("/agent/chat_text/{session_id}")
async def chat_text(session_id: str = Path(...), request: TextChatRequest = None):
    try:
        if not request or not request.user_text.strip():
            return await create_error_response(400, "Text input is required")

        user_text = request.user_text.strip()
        history = chat_history_store.get(session_id, [])
        history.append({"role": "user", "parts": [user_text]})
        llm_text = await generate_llm_response(history, user_text)
        history.append({"role": "model", "parts": [llm_text]})
        chat_history_store[session_id] = history

        audio_url = await generate_tts(llm_text)
        return {"user_text": user_text, "llm_response_text": llm_text, "llm_response_audio_url": audio_url}

    except Exception as e:
        return await create_error_response(500, str(e))
