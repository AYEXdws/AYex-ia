from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from backend.src.routes.deps import get_services
from backend.src.schemas import TTSRequest
from backend.src.services.container import BackendServices

router = APIRouter()


@router.post("/tts")
def tts(payload: TTSRequest, services: BackendServices = Depends(get_services)) -> Response:
    text = payload.text.strip()
    if not text:
        return Response(content=b"text bos", media_type="text/plain", status_code=400)
    wav_bytes = services.tts.synthesize_wav_bytes(
        text=text,
        voice=payload.voice or services.settings.default_voice,
        model=payload.model,
    )
    return Response(content=wav_bytes, media_type="audio/wav")
