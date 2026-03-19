from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
    openclaw_force_model: bool
    openclaw_max_output_tokens: int
    openclaw_instructions: str
    openclaw_timeout_sec: int
    openclaw_context_turns: int
    openclaw_cache_ttl_sec: int
    openclaw_cache_size: int
    audio_default_engine: str
    web_mvp_only: bool
    data_dir: str
    profile_path: str
    chat_dir: str
    daily_request_limit: int
    daily_input_char_limit: int


def load_settings() -> BackendSettings:
    openclaw_enabled_raw = os.environ.get("OPENCLAW_ENABLED", "true").strip().lower()
    openclaw_enabled = openclaw_enabled_raw in {"1", "true", "yes", "on"}
    web_mvp_only_raw = os.environ.get("AYEX_WEB_MVP_ONLY", "true").strip().lower()
    web_mvp_only = web_mvp_only_raw in {"1", "true", "yes", "on"}
    data_dir = Path(os.environ.get("AYEX_DATA_DIR", ".ayex")).expanduser().resolve()
    profile_path = Path(os.environ.get("AYEX_PROFILE_PATH") or str(data_dir / "profile.json")).expanduser().resolve()
    chat_dir = Path(os.environ.get("AYEX_CHAT_DIR") or str(data_dir / "chats")).expanduser().resolve()
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
        openclaw_force_model=(os.environ.get("OPENCLAW_FORCE_MODEL", "true").strip().lower() in {"1", "true", "yes", "on"}),
        openclaw_max_output_tokens=max(24, int(os.environ.get("OPENCLAW_MAX_OUTPUT_TOKENS", "80"))),
        openclaw_instructions=(
            os.environ.get("OPENCLAW_INSTRUCTIONS")
            or "Her zaman Turkce cevap ver. Kisa, net ve dogal yaz. Basit sorularda 2-4 cumle kullan; analiz gereken durumda maddeli ve yapisal yanit ver."
        ).strip(),
        openclaw_timeout_sec=max(4, int(os.environ.get("OPENCLAW_TIMEOUT_SEC", "12"))),
        openclaw_context_turns=max(0, min(12, int(os.environ.get("OPENCLAW_CONTEXT_TURNS", "6")))),
        openclaw_cache_ttl_sec=max(0, int(os.environ.get("OPENCLAW_CACHE_TTL_SEC", "45"))),
        openclaw_cache_size=max(8, int(os.environ.get("OPENCLAW_CACHE_SIZE", "128"))),
        audio_default_engine=(os.environ.get("AYEX_AUDIO_ENGINE_DEFAULT") or "openclaw").strip().lower(),
        web_mvp_only=web_mvp_only,
        data_dir=str(data_dir),
        profile_path=str(profile_path),
        chat_dir=str(chat_dir),
        daily_request_limit=max(10, int(os.environ.get("AYEX_DAILY_REQUEST_LIMIT", "350"))),
        daily_input_char_limit=max(1000, int(os.environ.get("AYEX_DAILY_INPUT_CHAR_LIMIT", "120000"))),
    )


def openai_api_key() -> str:
    # OPENAI_API_KEY is the primary key name.
    # AYEX_API_KEY is kept only as a legacy fallback for old env files.
    key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("AYEX_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY tanimli degil (AYEX_API_KEY legacy fallback da bos).")
    return key
