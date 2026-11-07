"""Optional server-side transcription (OpenAI) — the browser Web Speech API is the keyless default.
Either way the transcript is shown, editable, and submitted to the same /api/guide/ask path."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.get("/status")
async def status() -> dict:
    s = get_settings()
    return {"server_transcription": bool(s.openai_api_key), "model": s.openai_transcribe_model if s.openai_api_key else None, "browser_speech_recommended": True, "push_to_talk_only": True}


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    s = get_settings()
    if not s.openai_api_key:
        raise HTTPException(503, "Server transcription unconfigured: set OPENAI_API_KEY. The browser's push-to-talk speech recognition still works.")
    from openai import AsyncOpenAI

    data = await audio.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "Audio too large (15 MB max)")
    client = AsyncOpenAI(api_key=s.openai_api_key)
    result = await client.audio.transcriptions.create(model=s.openai_transcribe_model, file=(audio.filename or "audio.webm", data, audio.content_type or "audio/webm"))
    return {"transcript": result.text, "model": s.openai_transcribe_model}
