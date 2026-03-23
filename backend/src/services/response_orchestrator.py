from __future__ import annotations

from dataclasses import dataclass

from ayex_core.agent import AyexAgent

from backend.src.services.intent_router import IntentResult, IntentRouter
from backend.src.services.model_router import select_model
from backend.src.services.model_service import ModelService
from backend.src.services.stt_service import SpeechToTextService
from backend.src.services.tool_router import ToolRouter
from backend.src.services.tts_service import TextToSpeechService
from backend.src.services.voice_response import VoiceResponseService
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AudioTurnResult:
    transcript: str
    reply: str
    wav_bytes: bytes
    intent: IntentResult


class ResponseOrchestrator:
    def __init__(
        self,
        stt_service: SpeechToTextService,
        tts_service: TextToSpeechService,
        intent_router: IntentRouter,
        tool_router: ToolRouter,
        voice_response_service: VoiceResponseService,
        model_service: ModelService,
    ):
        self.stt_service = stt_service
        self.tts_service = tts_service
        self.intent_router = intent_router
        self.tool_router = tool_router
        self.voice_response_service = voice_response_service
        self.model_service = model_service

    def process_audio_turn(
        self,
        wav_bytes: bytes,
        agent: AyexAgent,
        voice: str,
        engine: str = "ayex",
        workspace: str | None = None,
        model: str | None = None,
    ) -> AudioTurnResult:
        transcript = self.stt_service.transcribe_wav_bytes(wav_bytes)
        intent = self.intent_router.route(transcript)
        if not transcript:
            return AudioTurnResult(
                transcript="",
                reply="",
                wav_bytes=b"",
                intent=intent,
            )

        selected = select_model(transcript)
        selected_model = selected.model
        selected_mode = selected.route
        selected_reason = selected.reason
        logger.info(
            "MODEL_SELECTED model=%s mode=%s reason=%s",
            selected_model,
            selected_mode,
            selected_reason,
        )

        result = self.model_service.run_action(
            transcript,
            workspace=workspace,
            model=model or selected_model,
            route_name="audio_turn",
        )
        fallback_model = (self.model_service.settings.ayex_fast_model or "gpt-4o").strip()
        if not result.ok and (model or selected_model) != fallback_model:
            logger.warning(
                "MODEL_FALLBACK_TRIGGER from_model=%s to_model=%s reason=primary_failed",
                model or selected_model,
                fallback_model,
            )
            result = self.model_service.run_action(
                transcript,
                workspace=workspace,
                model=fallback_model,
                route_name="audio_turn_fallback",
            )

        reply = result.text if result.ok else "Model yaniti alinamadi. Lutfen tekrar dene."
        logger.info(
            "AUDIO_ROUTE_REPLY source=%s ok=%s latency_ms=%s",
            result.source,
            result.ok,
            result.latency_ms,
        )

        wav_reply = self.tts_service.synthesize_wav_bytes(
            reply or "Model yaniti alinamadi. Lutfen tekrar dene.",
            voice=voice,
        )
        return AudioTurnResult(
            transcript=transcript,
            reply=reply,
            wav_bytes=wav_reply,
            intent=intent,
        )
