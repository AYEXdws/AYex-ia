from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BackendSettings:
    api_base_url: str
    stt_model: str
    tts_model: str
    default_voice: str
    retry_count: int
    openai_timeout_sec: int
    openclaw_enabled: bool
    openclaw_base_url: str
    openclaw_api_key: str
    openclaw_mode: str
    openclaw_action_path: str
    openclaw_model: str
    openclaw_max_output_tokens: int
    openclaw_instructions: str
    audio_default_engine: str
    web_mvp_only: bool


def load_settings() -> BackendSettings:
    openclaw_enabled_raw = os.environ.get("OPENCLAW_ENABLED", "true").strip().lower()
    openclaw_enabled = openclaw_enabled_raw in {"1", "true", "yes", "on"}
    web_mvp_only_raw = os.environ.get("AYEX_WEB_MVP_ONLY", "true").strip().lower()
    web_mvp_only = web_mvp_only_raw in {"1", "true", "yes", "on"}
    return BackendSettings(
        api_base_url=(os.environ.get("AYEX_API_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        stt_model=os.environ.get("AYEX_STT_MODEL", "gpt-4o-mini-transcribe"),
        tts_model=os.environ.get("AYEX_TTS_MODEL", "gpt-4o-mini-tts"),
        default_voice=os.environ.get("AYEX_DEFAULT_VOICE", "alloy"),
        retry_count=max(0, int(os.environ.get("AYEX_HTTP_RETRY_COUNT", "2"))),
        openai_timeout_sec=max(10, int(os.environ.get("AYEX_OPENAI_TIMEOUT_SEC", "45"))),
        openclaw_enabled=openclaw_enabled,
        openclaw_base_url=(os.environ.get("OPENCLAW_BASE_URL") or "http://127.0.0.1:18789").rstrip("/"),
        openclaw_api_key=(os.environ.get("OPENCLAW_API_KEY") or "").strip(),
        openclaw_mode=(os.environ.get("OPENCLAW_MODE") or "openai_chat_completions").strip().lower(),
        openclaw_action_path=(os.environ.get("OPENCLAW_ACTION_PATH") or "/action").strip(),
        openclaw_model=(os.environ.get("OPENCLAW_MODEL") or "openai/gpt-4o-mini").strip(),
        openclaw_max_output_tokens=max(24, int(os.environ.get("OPENCLAW_MAX_OUTPUT_TOKENS", "80"))),
        openclaw_instructions=(
            os.environ.get("OPENCLAW_INSTRUCTIONS")
            or "Her zaman Turkce cevap ver. Kisa, net ve dogal yaz. En fazla 3 cumle kullan."
        ).strip(),
        audio_default_engine=(os.environ.get("AYEX_AUDIO_ENGINE_DEFAULT") or "openclaw").strip().lower(),
        web_mvp_only=web_mvp_only,
    )


def openai_api_key() -> str:
    key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("AYEX_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY veya AYEX_API_KEY tanimli degil.")
    return key
