# AYEX Core Architecture (Refactored)

## Current runtime entrypoints

- Backend API: `python3 run_server.py`
- Terminal mode: `python3 run_terminal.py`
- ESP32 firmware (PlatformIO): `esp32-client/`
- Legacy Arduino sketches (kept for reference): `arduino/`

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
  tools/
  docs/
```

## Backend module responsibilities

- `backend/src/routes/`
  - HTTP layer only
  - request validation + response shaping
- `backend/src/services/stt_service.py`
  - speech-to-text calls
- `backend/src/services/tts_service.py`
  - text-to-speech calls
- `backend/src/services/intent_router.py`
  - first-pass intent classification
- `backend/src/services/tool_router.py`
  - cheap command handling (time/date/profile summary)
- `backend/src/services/response_orchestrator.py`
  - end-to-end speech turn orchestration
- `backend/src/services/agent_registry.py`
  - `AyexAgent` lifecycle/cache per workspace/model
- `backend/src/memory/manager.py`
  - memory facade for profile/recent context
- `backend/src/config/env.py`
  - centralized env + model settings
- `backend/src/utils/logging.py`
  - logger bootstrap

## ESP32 module responsibilities

- `esp32-client/src/main.cpp`
  - audio capture (INMP441 / I2S RX)
  - network client (Wi-Fi + multipart POST)
  - request/response handling (`/voice/turn` compatibility path)
  - audio playback (MAX98357 / I2S TX)
- `esp32-client/include/device_config.h`
  - pins, thresholds, backend host/path, voice settings

## Compatibility note

`POST /voice/turn` is preserved as an alias of `POST /audio` so existing deployed firmware keeps working without protocol changes.
