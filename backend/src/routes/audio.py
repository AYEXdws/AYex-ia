from __future__ import annotations

import traceback
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices
from backend.src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


async def _handle_audio_turn(
    *,
    audio: UploadFile,
    workspace: Optional[str],
    model: Optional[str],
    voice: str,
    engine: Optional[str],
    services: BackendServices,
) -> Response:
    try:
        wav_bytes = await audio.read()
        if not wav_bytes:
            return Response(content=b"audio bos", media_type="text/plain", status_code=400)

        agent = services.agents.get_agent(workspace, model)
        selected_engine = (engine or services.settings.audio_default_engine or "ayex").strip().lower()
        turn = services.orchestrator.process_audio_turn(
            wav_bytes=wav_bytes,
            agent=agent,
            voice=voice,
            engine=selected_engine,
            workspace=workspace,
            model=model,
        )

        if not turn.transcript:
            return Response(content=b"", media_type="audio/wav", headers={"X-Transcript": "", "X-Reply": ""})

        safe_transcript = quote(turn.transcript, safe="")[:1024]
        safe_reply = quote(turn.reply, safe="")[:1024]
        return Response(
            content=turn.wav_bytes,
            media_type="audio/wav",
            headers={
                "X-Transcript": safe_transcript,
                "X-Reply": safe_reply,
                "X-Intent": turn.intent.category,
                "X-Engine": selected_engine,
            },
        )
    except Exception as exc:
        traceback.print_exc()
        msg = f"voice_turn_error: {type(exc).__name__}: {exc}"
        logger.exception("audio_turn_failed")
        return Response(content=msg.encode("utf-8", errors="ignore"), media_type="text/plain", status_code=500)


@router.post("/audio")
async def audio_turn(
    audio: UploadFile = File(...),
    workspace: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    voice: str = Form("alloy"),
    engine: Optional[str] = Form(None),
    services: BackendServices = Depends(get_services),
) -> Response:
    return await _handle_audio_turn(
        audio=audio,
        workspace=workspace,
        model=model,
        voice=voice,
        engine=engine,
        services=services,
    )


@router.post("/voice/turn")
async def voice_turn_compat(
    audio: UploadFile = File(...),
    workspace: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    voice: str = Form("alloy"),
    engine: Optional[str] = Form(None),
    services: BackendServices = Depends(get_services),
) -> Response:
    # Backward-compatible alias for existing ESP32 firmware.
    return await _handle_audio_turn(
        audio=audio,
        workspace=workspace,
        model=model,
        voice=voice,
        engine=engine,
        services=services,
    )
