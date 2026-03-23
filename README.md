# AYEX-IA

AYEX-IA, Ahmet icin gelistirilen kisisel analiz ve karar destek altyapisidir.

Sistem hedefi:
- n8n uzerinden gelen guncel istihbarat verisini (kripto, dunya haberleri, siber guvenlik, makro) LLM'e dogrudan vermek
- Ahmet'in profil ve hafiza baglamini her mesajda kullanmak
- gereksiz ara katmanlari azaltip basit, hizli ve guvenilir bir chat akisiyla cevap uretmek

## Mimari ozet

- Backend: FastAPI (`backend/src`)
- Frontend: React/Vite (`frontend/src`)
- Model gateway: dogrudan provider SDK
  - Anthropic (Claude)
  - OpenAI (GPT)
- Veri depolari:
  - sohbet oturumlari (`.ayex/chats`)
  - profil (`.ayex/profile.json`)
  - intel event store + arsiv

OpenClaw bridge bu repoda aktif akisdan kaldirilmistir.

## API yuzeyi

- `GET /health`
- `POST /chat`
- `POST /action`
- `GET /profile`
- `PATCH /profile`
- `GET /sessions`
- `POST /sessions`
- `GET /sessions/{session_id}/messages`
- `DELETE /sessions/{session_id}`
- `GET /usage`
- `POST /events/ingest`

`AYEX_WEB_MVP_ONLY=false` oldugunda ses endpointleri de acilir:
- `POST /audio`
- `POST /voice/turn`
- `POST /tts`
- `POST /event`

## Hızlı baslatma

```bash
pip install -r requirements.txt
cp .env.example .env
# .env icine OPENAI_API_KEY yaz; Claude kullanacaksan ANTHROPIC_API_KEY de gir
./run_mvp.sh
```

Ac:
- [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## Ortam degiskenleri

Zorunlu:
- `OPENAI_API_KEY` (veya legacy fallback: `AYEX_API_KEY`)

Opsiyonel model routing:
- `ANTHROPIC_API_KEY`
- `AYEX_CHAT_MODEL` (default `claude-haiku-4.5`)
- `AYEX_REASONING_MODEL` (default `claude-sonnet-4.6`)
- `AYEX_POWER_MODEL` (default `gpt-5`)
- `AYEX_FAST_MODEL` (default `gpt-4o-mini`)

Model ayarlari:
- `AYEX_MODEL_MAX_OUTPUT_TOKENS`
- `AYEX_MODEL_CONTEXT_TURNS`
- `AYEX_MODEL_CACHE_TTL_SEC`
- `AYEX_MODEL_CACHE_SIZE`
- `AYEX_INTEL_PROMPT_MAX_EVENTS`
- `AYEX_INTEL_PROMPT_MAX_CHARS`
- `AYEX_MODEL_INSTRUCTIONS` (opsiyonel override)

Uygulama ayarlari:
- `AYEX_WEB_MVP_ONLY`
- `AYEX_DATA_DIR`
- `AYEX_PROFILE_PATH`
- `AYEX_CHAT_DIR`
- `AYEX_DAILY_REQUEST_LIMIT`
- `AYEX_DAILY_INPUT_CHAR_LIMIT`
- `AYEX_INTEL_INGEST_TOKEN` (opsiyonel ikinci katman token kontrolu)
- `AYEX_INTEL_INGEST_RPM` (`/events/ingest` dakika basi limit)
- `AYEX_AUDIO_ENGINE_DEFAULT` (default `openai`)
- `AYEX_STT_MODEL`, `AYEX_TTS_MODEL`, `AYEX_DEFAULT_VOICE`

## Evrim notlari

- Chat akisinda ana strateji: tum guncel intel verisini LLM'e ver, kod tarafinda asiri filtreleme yapma.
- Market tool zorunlu degil; birincil kaynak intel feed'dir.
- Sahte seed event uretimi kaldirildi; veri yoksa sistem bunu durustce belirtir.

## Faydali dokumanlar

- `VISION.md`
- `CORE_IDENTITY.md`
- `ARCHITECTURE.md`
- `PROJECT_STATE.md`
- `PHASES.md`
- `AI_HANDOFF.md`
- `SYSTEM_RULES.md`
- `N8N_MAP.md`
