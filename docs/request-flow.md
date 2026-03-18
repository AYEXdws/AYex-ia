# Request Flow

## End-to-end voice path

1. User speaks
2. ESP32 records PCM16 frames (24 kHz mono)
3. ESP32 sends WAV payload to backend (`POST /voice/turn` or `POST /audio`)
4. Backend STT service transcribes audio
5. Backend intent router classifies request:
   - `simple_command`
   - `question`
   - `conversation`
   - `memory_request`
   - `future_device_action`
6. Tool router handles cheap commands when possible (no expensive LLM call)
7. Fallback/normal path uses AYEX voice response logic + memory context
8. Backend TTS service generates WAV audio reply
9. Backend returns playable WAV bytes to ESP32
10. ESP32 parses WAV and streams PCM to MAX98357/speaker

## HTTP routes

- `GET /health`
- `POST /chat` (text in, text out)
- `POST /audio` (multipart audio in, wav out)
- `POST /voice/turn` (compatibility alias for existing ESP32)
- `POST /tts` (text in, wav out)
- `POST /event` (reserved for future sensor/event ingress)

## Current ESP32 audio request format

Multipart fields currently expected by backend:

- `workspace` (string, optional)
- `voice` (string, optional; default: `alloy`)
- `audio` (WAV file)

Response:

- `Content-Type: audio/wav`
- headers: `X-Transcript`, `X-Reply`, `X-Intent`
