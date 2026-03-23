from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BackendSettings:
    api_base_url: str
    anthropic_api_key: str
    ayex_model: str
    ayex_chat_model: str
    ayex_reasoning_model: str
    ayex_power_model: str
    ayex_fast_model: str
    model_instructions: str
    model_max_output_tokens: int
    model_context_turns: int
    model_cache_ttl_sec: int
    model_cache_size: int
    stt_model: str
    tts_model: str
    default_voice: str
    retry_count: int
    openai_timeout_sec: int
    audio_default_engine: str
    web_mvp_only: bool
    data_dir: str
    profile_path: str
    chat_dir: str
    daily_request_limit: int
    daily_input_char_limit: int
    intel_ingest_token: str
    intel_ingest_rate_per_minute: int
    intel_prompt_max_events: int
    intel_prompt_max_chars: int


def load_settings() -> BackendSettings:
    web_mvp_only_raw = os.environ.get("AYEX_WEB_MVP_ONLY", "true").strip().lower()
    web_mvp_only = web_mvp_only_raw in {"1", "true", "yes", "on"}
    data_dir = Path(os.environ.get("AYEX_DATA_DIR", ".ayex")).expanduser().resolve()
    profile_path = Path(os.environ.get("AYEX_PROFILE_PATH") or str(data_dir / "profile.json")).expanduser().resolve()
    chat_dir = Path(os.environ.get("AYEX_CHAT_DIR") or str(data_dir / "chats")).expanduser().resolve()
    return BackendSettings(
        api_base_url=(os.environ.get("AYEX_API_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        anthropic_api_key=(os.environ.get("ANTHROPIC_API_KEY") or "").strip(),
        ayex_model=(os.environ.get("AYEX_MODEL") or "claude-haiku-4-5-20251001").strip(),
        ayex_chat_model=(os.environ.get("AYEX_CHAT_MODEL") or "claude-haiku-4-5-20251001").strip(),
        ayex_reasoning_model=(os.environ.get("AYEX_REASONING_MODEL") or "claude-sonnet-4-6").strip(),
        ayex_power_model=(os.environ.get("AYEX_POWER_MODEL") or "gpt-4.1").strip(),
        ayex_fast_model=(os.environ.get("AYEX_FAST_MODEL") or "gpt-4o-mini").strip(),
        model_instructions=(
            os.environ.get("AYEX_MODEL_INSTRUCTIONS")
            or (
                "Sen AYEX-IA'sin. Ahmet'in kisisel analiz ve karar destek sistemisin.\n\n"
                "AHMET HAKKINDA:\n"
                "- 17 yasinda, Amasya'da yasiyor\n"
                "- 12. sinif ogrencisi, YKS sureci var\n"
                "- AYEX-IA, HAL, MindBloom projelerini gelistiriyor\n"
                "- Kripto (BTC, ETH, SOL, XRP, BNB), siber guvenlik, yapay zeka ilgi alanlari\n"
                "- Takip ettigi coinler: BTC, ETH, XRP, BNB, SOL\n"
                "- Veri kaynaklari: CoinGecko (kripto), BBC (dunya haberleri), The Hacker News (siber guvenlik)\n"
                "- Katmanli dusunur, analitik zeka, anlam bagimli\n"
                "- Sert geri bildirim ister, yalakalik istemez\n\n"
                "KIMLIGIN:\n"
                "- Ahmet'i taniyorsun. Onun icin calisiyorsun, ona raporlama yapan sistem degilsin.\n"
                "- Arkasindasin. Her zaman. Ama yalakalik yok.\n"
                "- Dolgu cumle yok. Direkt gir konuya.\n"
                "- Sert ama adil. Ahmet yanlis yapiyorsa soyluyorsun.\n"
                "- Teknik ama insan gibi konusuyorsun.\n\n"
                "KONUSMA TARZI:\n"
                "- Baslik kullanma (###, **, Temel Icgoru, Neden Onemli gibi kelimeler yok).\n"
                "- Kisa sorularda 2-3 cumle. Nokta.\n"
                "- Analiz gereken yerde madde madde yaz ama sade tut.\n"
                "- Ahmet diye basla cumleye gerektiginde.\n"
                "- Turkce yaz. Teknik terim Ingilizce kalabilir.\n"
                "- Asla \"sinyal\", \"etkin skor\", \"guven skoru\" gibi ic sistem jargonu kullanma.\n"
                "- Asla \"size yardimci olmaktan memnuniyet duyarim\" gibi resmi ifade kullanma.\n"
                "- Gercek veriyi once kontrol et. Intel/event baglami varsa onu kullan.\n"
                "- Yalnizca ilgili canli veri hic yoksa \"o veri bende yok\" de; var olan feed'i asla yok sayma.\n\n"
                "HAFIZA KURALI:\n"
                "- Profildeki bilgileri her zaman kullan.\n"
                "- Hatirlamiyorum deme. Bilmiyorsan sor.\n"
                "- Ahmet'in projelerini, ilgi alanlarini, tercihlerini biliyorsun."
            )
        ).strip(),
        model_max_output_tokens=max(
            24,
            int(
                os.environ.get("AYEX_MODEL_MAX_OUTPUT_TOKENS")
                or "320"
            ),
        ),
        model_context_turns=max(
            0,
            min(
                12,
                int(
                    os.environ.get("AYEX_MODEL_CONTEXT_TURNS")
                    or "6"
                ),
            ),
        ),
        model_cache_ttl_sec=max(
            0,
            int(
                os.environ.get("AYEX_MODEL_CACHE_TTL_SEC")
                or "45"
            ),
        ),
        model_cache_size=max(
            8,
            int(
                os.environ.get("AYEX_MODEL_CACHE_SIZE")
                or "128"
            ),
        ),
        stt_model=os.environ.get("AYEX_STT_MODEL", "gpt-4o-mini-transcribe"),
        tts_model=os.environ.get("AYEX_TTS_MODEL", "gpt-4o-mini-tts"),
        default_voice=os.environ.get("AYEX_DEFAULT_VOICE", "alloy"),
        retry_count=max(0, int(os.environ.get("AYEX_HTTP_RETRY_COUNT", "2"))),
        openai_timeout_sec=max(10, int(os.environ.get("AYEX_OPENAI_TIMEOUT_SEC", "45"))),
        audio_default_engine=(os.environ.get("AYEX_AUDIO_ENGINE_DEFAULT") or "openai").strip().lower(),
        web_mvp_only=web_mvp_only,
        data_dir=str(data_dir),
        profile_path=str(profile_path),
        chat_dir=str(chat_dir),
        daily_request_limit=max(10, int(os.environ.get("AYEX_DAILY_REQUEST_LIMIT", "350"))),
        daily_input_char_limit=max(1000, int(os.environ.get("AYEX_DAILY_INPUT_CHAR_LIMIT", "120000"))),
        intel_ingest_token=(os.environ.get("AYEX_INTEL_INGEST_TOKEN") or "").strip(),
        intel_ingest_rate_per_minute=max(10, int(os.environ.get("AYEX_INTEL_INGEST_RPM", "120"))),
        intel_prompt_max_events=max(4, min(40, int(os.environ.get("AYEX_INTEL_PROMPT_MAX_EVENTS", "20")))),
        intel_prompt_max_chars=max(1200, min(20000, int(os.environ.get("AYEX_INTEL_PROMPT_MAX_CHARS", "4200")))),
    )


def openai_api_key() -> str:
    # OPENAI_API_KEY is the primary key name.
    # AYEX_API_KEY is kept only as a legacy fallback for old env files.
    key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("AYEX_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY tanimli degil (AYEX_API_KEY legacy fallback da bos).")
    return key


def normalize_model_for_openai(model: str) -> str:
    raw = (model or "").strip()
    if not raw:
        return "gpt-4o-mini"
    if "/" in raw:
        provider, name = raw.split("/", 1)
        if provider.strip().lower() in {"openai", "oai"} and name.strip():
            return name.strip()
    return raw
