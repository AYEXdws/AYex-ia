from __future__ import annotations

from urllib import request as urlrequest

from backend.src.config.env import BackendSettings, openai_api_key
from backend.src.services.http_utils import multipart_body, parse_json_bytes, with_retries


class SpeechToTextService:
    def __init__(self, settings: BackendSettings):
        self.settings = settings

    def transcribe_wav_bytes(self, wav_bytes: bytes, model: str | None = None, language: str = "tr") -> str:
        chosen_model = model or self.settings.stt_model

        def _call() -> str:
            boundary, body = multipart_body(
                fields={"model": chosen_model, "language": language},
                file_field="file",
                filename="audio.wav",
                content_type="audio/wav",
                payload=wav_bytes,
            )
            req = urlrequest.Request(
                f"{self.settings.api_base_url}/audio/transcriptions",
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {openai_api_key()}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
            )
            with urlrequest.urlopen(req, timeout=120) as resp:
                data = parse_json_bytes(resp.read())
            return str(data.get("text", "")).strip()

        return str(with_retries(_call, "transcribe", retries=self.settings.retry_count))
