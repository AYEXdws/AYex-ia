from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backend.src.config.env import BackendSettings


def make_settings(tmp_path: Path) -> BackendSettings:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    chats = data_dir / "chats"
    chats.mkdir(parents=True, exist_ok=True)
    profile_path = data_dir / "profile.json"
    profile_path.write_text("{}", encoding="utf-8")
    return BackendSettings(
        api_base_url="https://api.openai.com/v1",
        anthropic_api_key="",
        ayex_model="claude-haiku-4-5-20251001",
        ayex_chat_model="claude-haiku-4-5-20251001",
        ayex_reasoning_model="claude-sonnet-4-6",
        ayex_power_model="gpt-4.1",
        ayex_fast_model="gpt-4o",
        model_instructions="test instructions",
        model_max_output_tokens=320,
        model_context_turns=6,
        model_cache_ttl_sec=45,
        model_cache_size=128,
        stt_model="gpt-4o-mini-transcribe",
        tts_model="gpt-4o-mini-tts",
        default_voice="alloy",
        retry_count=1,
        openai_timeout_sec=30,
        audio_default_engine="openai",
        web_mvp_only=True,
        data_dir=str(data_dir),
        profile_path=str(profile_path),
        chat_dir=str(chats),
        daily_request_limit=350,
        daily_input_char_limit=120000,
        intel_ingest_token="",
        intel_ingest_rate_per_minute=120,
        intel_prompt_max_events=20,
        intel_prompt_max_chars=4200,
    )
