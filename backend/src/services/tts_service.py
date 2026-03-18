from __future__ import annotations

import json
from urllib import request as urlrequest

from backend.src.config.env import BackendSettings, openai_api_key
from backend.src.services.http_utils import with_retries


class TextToSpeechService:
    def __init__(self, settings: BackendSettings):
        self.settings = settings

    def synthesize_wav_bytes(self, text: str, voice: str | None = None, model: str | None = None) -> bytes:
        chosen_voice = voice or self.settings.default_voice
        chosen_model = model or self.settings.tts_model

        def _call() -> bytes:
            payload = {
                "model": chosen_model,
                "voice": chosen_voice,
                "input": text,
                "response_format": "wav",
            }
            if chosen_model == "gpt-4o-mini-tts":
                payload["instructions"] = "Turkce, kisa, net, dogal konus."
            req = urlrequest.Request(
                f"{self.settings.api_base_url}/audio/speech",
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={
                    "Authorization": f"Bearer {openai_api_key()}",
                    "Content-Type": "application/json",
                },
            )
            with urlrequest.urlopen(req, timeout=120) as resp:
                return resp.read()

        return bytes(with_retries(_call, "tts", retries=self.settings.retry_count))
