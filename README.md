# AYEX

Incrementally refactored physical AI assistant stack for ESP32-S3 + cloud backend.

This refactor preserves the working prototype behavior while reorganizing the codebase into clearer modules and adding a PlatformIO-compatible ESP32 client project.

## Runtime mode

- Text reasoning engine is selectable:
  - `OPENCLAW_ENABLED=true`: OpenClaw bridge path
  - `OPENCLAW_ENABLED=false`: direct OpenAI path (no OpenClaw request)
- Web MVP default: `AYEX_WEB_MVP_ONLY=true` (only web/chat/action/health routes are active).
- Jarvis-style web console includes persistent chat sessions and profile-aware responses.
- Voice/ESP32 routes stay available for later phases by setting `AYEX_WEB_MVP_ONLY=false`.

## Backend API surface

- `GET /health`
- `POST /chat`
- `POST /action`
- `GET /profile`
- `PATCH /profile`
- `GET /sessions`
- `POST /sessions`
- `GET /sessions/{session_id}/messages`
- `DELETE /sessions/{session_id}`
- `POST /audio` (only when `AYEX_WEB_MVP_ONLY=false`)
- `POST /voice/turn` (only when `AYEX_WEB_MVP_ONLY=false`)
- `POST /tts` (only when `AYEX_WEB_MVP_ONLY=false`)
- `POST /event` (only when `AYEX_WEB_MVP_ONLY=false`)

## Repository layout

```text
project-root/
  backend/
    src/
      config/
      memory/
      routes/
      services/
      utils/
      index.py
  esp32-client/
    platformio.ini
    include/
    src/
    lib/
  src/
    ayex_core/
    ayex_api/
  arduino/
  tools/
  docs/
```

## MVP quick start

```bash
pip install -r requirements.txt
cp .env.example .env
# .env icine OPENAI_API_KEY ve OPENCLAW_API_KEY degerlerini gir
./setup_openclaw_features.sh
./run_mvp.sh
```

Open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`

Environment:

- `OPENAI_API_KEY` or `AYEX_API_KEY` (required)
- optional: `AYEX_API_BASE_URL`, `AYEX_STT_MODEL`, `AYEX_TTS_MODEL`, `AYEX_DEFAULT_VOICE`
- OpenClaw bridge: `OPENCLAW_ENABLED=true`, `OPENCLAW_BASE_URL=http://127.0.0.1:18789`, `OPENCLAW_API_KEY=...`
- Direct OpenAI mode: `OPENCLAW_ENABLED=false` (OpenClaw gateway kontrolu/istegi yapilmaz)
- OpenClaw mode: `OPENCLAW_MODE=openai_chat_completions`
- OpenClaw model lock: `OPENCLAW_MODEL=openai/gpt-4o-mini`, `OPENCLAW_FORCE_MODEL=true`
- OpenClaw output budget: `OPENCLAW_MAX_OUTPUT_TOKENS=80`
- OpenClaw feature bootstrap vars:
  - `OPENCLAW_PUBLIC_URL=ws://127.0.0.1:18789`
  - `OPENCLAW_HOOKS_TOKEN=...` (opsiyonel; verilmezse otomatik uretilir)
  - `OPENCLAW_CRON_WEBHOOK_TOKEN=...` (opsiyonel; verilmezse otomatik uretilir)
  - `OPENCLAW_OTEL_ENABLED=false`
  - `OPENCLAW_OTEL_ENDPOINT=http://127.0.0.1:4318` (opsiyonel)
- OpenClaw low-latency controls: `OPENCLAW_TIMEOUT_SEC=12`, `OPENCLAW_CONTEXT_TURNS=6`, `OPENCLAW_CACHE_TTL_SEC=45`, `OPENCLAW_CACHE_SIZE=128`
- Cost guard controls: `AYEX_DAILY_REQUEST_LIMIT=350`, `AYEX_DAILY_INPUT_CHAR_LIMIT=120000`
- OpenClaw response language: `OPENCLAW_INSTRUCTIONS=Her zaman Turkce cevap ver. Kisa, net ve dogal yaz. Basit sorularda 2-4 cumle kullan; analiz gereken durumda maddeli ve yapisal yanit ver.`
- web-only MVP toggle: `AYEX_WEB_MVP_ONLY=true`
- local data paths: `AYEX_DATA_DIR=.ayex`, `AYEX_PROFILE_PATH=.ayex/profile.json`, `AYEX_CHAT_DIR=.ayex/chats`
- audio default engine (ESP32 dahil): `AYEX_AUDIO_ENGINE_DEFAULT=openclaw`

Quick local OpenClaw bridge setup:

```bash
export OPENCLAW_ENABLED=true
export OPENCLAW_BASE_URL=http://127.0.0.1:18789
export OPENCLAW_MODE=openai_chat_completions
export OPENCLAW_MODEL=openai/gpt-4o-mini
export OPENCLAW_FORCE_MODEL=true
export OPENCLAW_MAX_OUTPUT_TOKENS=80
export OPENCLAW_TIMEOUT_SEC=12
export OPENCLAW_CONTEXT_TURNS=6
export OPENCLAW_CACHE_TTL_SEC=45
export OPENCLAW_CACHE_SIZE=128
export OPENCLAW_INSTRUCTIONS="Her zaman Turkce cevap ver. Kisa, net ve dogal yaz. Basit sorularda 2-4 cumle kullan; analiz gereken durumda maddeli ve yapisal yanit ver."
export AYEX_DATA_DIR=.ayex
export AYEX_PROFILE_PATH=.ayex/profile.json
export AYEX_CHAT_DIR=.ayex/chats
export AYEX_DAILY_REQUEST_LIMIT=350
export AYEX_DAILY_INPUT_CHAR_LIMIT=120000
export AYEX_AUDIO_ENGINE_DEFAULT=openclaw
# export OPENCLAW_API_KEY=...
```

Web UI:

- `GET /` Jarvis tarzı OpenClaw web panelidir.
- Sohbet istekleri `POST /action` endpointine gider.
- Oturum geçmişi ve profil bilgisi `sessions/profile` endpointlerinden okunur.
- Günlük kullanım metrikleri: `GET /usage`

## OpenClaw feature integration

`setup_openclaw_features.sh` su bileşenleri guvenli varsayilanlarla aktive eder:

- `memory-lancedb` (slot/memory aktif)
- `voice-call` (mock provider; local gelistirme icin)
- `talk-voice`
- `device-pair`
- `diagnostics-otel` + diagnostics config
- `cron` scheduler
- `hooks` (webhook ingest)

Komut:

```bash
./setup_openclaw_features.sh
```

Tokenlar:

- Script, webhook/cron tokenlarini `~/.openclaw/ayex-integration.tokens` dosyasina yazar.
- OpenClaw config dosyasinin timestampli yedegi de otomatik olusturulur.

## Direct OpenAI mode (OpenClaw off)

OpenClaw timeout/bridge bagimliligini gecici kapatmak icin:

```bash
export OPENCLAW_ENABLED=false
./run_mvp.sh
```

Bu modda:
- `/chat` ve `/action` dogrudan OpenAI istemcisi ile calisir.
- `localhost:18789` kontrolu/istegi yapilmaz.

## ESP32 PlatformIO run

```bash
cd esp32-client
pio run
pio run -t upload
pio device monitor
```

Before upload, edit `esp32-client/include/device_config.h`:

- Wi-Fi SSID/password
- backend host/port/path

Default firmware path uses `AYEX_VOICE_PATH = "/voice/turn"` for backward compatibility.

## Voice pipeline summary

1. ESP32 captures mic audio (INMP441, 24kHz PCM16)
2. ESP32 POSTs WAV to backend (`/voice/turn` or `/audio`)
3. Backend transcribes audio
4. Intent router decides cheap tool path vs normal conversational path
5. Backend synthesizes reply WAV
6. ESP32 plays WAV via MAX98357 + speaker

## Notes

- `src/ayex_api/server.py` is now a compatibility wrapper that imports the modular backend app from `backend/src/index.py`.
- Legacy Arduino IDE sketches are kept under `arduino/` as non-destructive reference.

## Additional docs

- `docs/architecture-overview.md`
- `docs/request-flow.md`
- `docs/platformio-esp32.md`
- `docs/future-phases.md`
