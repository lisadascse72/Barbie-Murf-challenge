from pydantic import BaseModel

class TTSRequest(BaseModel):
    text: str
    voiceId: str = "en-US-terrell"
    format: str = "MP3"

class TextChatRequest(BaseModel):
    user_text: str
