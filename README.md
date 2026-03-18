# AYEX

Incrementally refactored physical AI assistant stack for ESP32-S3 + cloud backend.

This refactor preserves the working prototype behavior while reorganizing the codebase into clearer modules and adding a PlatformIO-compatible ESP32 client project.

## Runtime mode

- OpenClaw is the primary/only text reasoning engine.
- Web MVP default: `AYEX_WEB_MVP_ONLY=true` (only web/chat/action/health routes are active).
- Voice/ESP32 routes stay available for later phases by setting `AYEX_WEB_MVP_ONLY=false`.

## Backend API surface

- `GET /health`
- `POST /chat`
- `POST /action`
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
./run_mvp.sh
```

Open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`

Environment:

- `OPENAI_API_KEY` or `AYEX_API_KEY` (required)
- optional: `AYEX_API_BASE_URL`, `AYEX_STT_MODEL`, `AYEX_TTS_MODEL`, `AYEX_DEFAULT_VOICE`
- OpenClaw bridge: `OPENCLAW_ENABLED=true`, `OPENCLAW_BASE_URL=http://127.0.0.1:18789`, `OPENCLAW_API_KEY=...`
- OpenClaw mode: `OPENCLAW_MODE=openai_chat_completions`
- OpenClaw model/latency: `OPENCLAW_MODEL=openai/gpt-4o-mini`, `OPENCLAW_MAX_OUTPUT_TOKENS=80`
- OpenClaw response language: `OPENCLAW_INSTRUCTIONS=Her zaman Turkce cevap ver. Kisa, net ve dogal yaz. En fazla 3 cumle kullan.`
- web-only MVP toggle: `AYEX_WEB_MVP_ONLY=true`
- audio default engine (ESP32 dahil): `AYEX_AUDIO_ENGINE_DEFAULT=openclaw`

Quick local OpenClaw bridge setup:

```bash
export OPENCLAW_ENABLED=true
export OPENCLAW_BASE_URL=http://127.0.0.1:18789
export OPENCLAW_MODE=openai_chat_completions
export OPENCLAW_MODEL=openai/gpt-4o-mini
export OPENCLAW_MAX_OUTPUT_TOKENS=80
export OPENCLAW_INSTRUCTIONS="Her zaman Turkce cevap ver. Kisa, net ve dogal yaz. En fazla 3 cumle kullan."
export AYEX_AUDIO_ENGINE_DEFAULT=openclaw
# export OPENCLAW_API_KEY=...
```

Web UI:

- `GET /` OpenClaw web panelidir.
- Sohbet istekleri `POST /action` endpointine gider.

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
