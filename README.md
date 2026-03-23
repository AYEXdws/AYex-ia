# AYEX-IA

AYEX-IA, Ahmet icin gelistirilen kisisel analiz, karar destek ve istihbarat birlestirme sistemidir.

Bu README proje icin tek teknik referans olacak sekilde yazildi. Buradaki amac, depoyu ilk kez acan birinin sistemin ne yaptigini, hangi dosyanin hangi gorevi ustlendigiini ve runtime'da ne oldugunu dosya isimleriyle gorebilmesidir.

## 1) Vizyon ve Sistem Ilkeleri

1. Intel-first: n8n feed'lerinden gelen guncel event verisi her mesajda kullanilir.
2. LLM-centric reasoning: kod yalnizca guardrail koyar, asil cikarim model tarafinda yapilir.
3. Basit ama saglam akis: gereksiz ara katmanlar azaltilir, kritik noktalarda guvenlik ve dayaniklilik artırılır.
4. Multi-model routing: sohbet/analiz/strateji icin farkli modeller secilebilir.
5. Operasyonel izlenebilirlik: request, model, ingest ve guard metrikleri loglanir.

## 2) Cekirdek Runtime Ozeti

Backend (FastAPI) bir service container olusturur ve tum route'lara ayni service graph'i inject eder.

1. Request -> middleware zinciri (`RequestMetricsMiddleware`, `AuthMiddleware`)
2. Route -> ilgili service'leri cagirma
3. ModelService -> Anthropic/OpenAI dogrudan cagrisi
4. ChatStore + Memory + IntelStore -> kalici state
5. Response -> `x-request-id` ve `x-response-time-ms` header'lari ile donus

## 3) Hızlı Baslatma

### Local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./run_mvp.sh
```

Ac:
- [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- [http://127.0.0.1:8000/health/ready](http://127.0.0.1:8000/health/ready)

### Render

`render.yaml` dogrudan `python run_server.py` ile ayağa kalkar.

Deploy standardi:
1. `OPENAI_API_KEY` zorunlu
2. `ANTHROPIC_API_KEY` opsiyonel
3. model ve intel budget env'leri render'da da ayni adlarla tanimli
4. ingest token gerekiyorsa `AYEX_INTEL_INGEST_TOKEN` secret olarak set edilir

## 4) End-to-End Akislar

### 4.1 `/chat` akisi

Dosya: `backend/src/routes/chat.py`

1. Guard kontrolu: `cost_guard.check_and_track(text)`
2. Session/duplicate kontrolu: `chat_store.ensure_session` + `recent_assistant_for_duplicate`
3. Kullanici mesaji kaydi: `chat_store.append_message(... role='user')`
4. Tum intel event'leri cekilir: `services.intel.store.get_all_events()`
5. Prompt budget ile event text olusturulur: `_format_all_events(max_events, max_chars)`
6. Memory + profile baglami cekilir
7. System prompt birlestirilir: `_build_system_prompt(...)`
8. Basit model secimi: `_select_model_simple(...)`
9. Model cagrisi: `services.model.run_action(...)`
10. Asistan mesaji kaydi + long memory append
11. Arka plan memory summary tetigi (`_maybe_trigger_memory_summary`)

Not: Memory summary hataya dusurse retry queue'ya alinip sonraki turlarda `process_retry_queue` ile tekrar denenir.

### 4.2 `/action` akisi

Dosya: `backend/src/routes/action.py`

1. Guard + dedup
2. Intent tespiti (`IntentRouter`)
3. ToolRouter ile kanit toplama (policy/timeout/cap uygulanmis)
4. Style + profile + memory baglami birlestirme
5. Agent mode veya normal model cagrisi
6. Sonucun chat store ve long memory'e yazilmasi

### 4.3 `/events/ingest` akisi

Dosya: `backend/src/routes/events.py`

1. Opsiyonel ingest token kontrolu (`AYEX_INTEL_INGEST_TOKEN`)
2. Kaynak/IP bazli RPM limit kontrolu (`AYEX_INTEL_INGEST_RPM`)
3. Payload parse + legacy wrapper merge
4. `IntelService.validate_event_payload` ile schema dogrulama
5. `intel.create_event(...)` ile skorlayip store'a yazma
6. long memory event append

### 4.4 Ses akislari (`/audio`, `/voice/turn`, `/tts`)

Dosyalar: `backend/src/routes/audio.py`, `backend/src/routes/tts.py`, `backend/src/services/response_orchestrator.py`

1. WAV alinir
2. STT -> intent -> model -> TTS zinciri calisir
3. WAV cevap ve transcript header'lari donulur

## 5) Multi-Model Katmani

Dosyalar:
- `backend/src/services/model_router.py`
- `backend/src/services/model_service.py`
- `backend/src/services/openai_client.py`
- `backend/src/services/anthropic_client.py`

Calisma prensibi:
1. ModelRouter route secer (`chat`, `reasoning`, `power`, `fast`)
2. ModelService secilen modele gore provider cagrisi yapar
3. Claude model adlari AnthropicClient'a gider
4. Digerleri OpenAIDirectClient'a gider
5. GPT-5 icin `temperature` gonderilmez
6. Kucuk in-memory cache ile kisa sureli duplicate cevap maliyeti azaltilir

## 6) Intel Katmani

Dosyalar:
- `backend/src/intel/event_model.py`
- `backend/src/intel/intel_service.py`
- `backend/src/intel/intel_store.py`
- `backend/src/intel/intel_archive.py`

Ozellikler:
1. Event schema normalize ve whitelist
2. Skorlama (`importance/urgency/confidence/final_score`)
3. `intel_events.json` disk persist
4. gunluk archive dosyalari (`.ayex/archive/YYYY-MM-DD.json`)
5. restart sonrasi archive restore

## 7) Memory Katmani

Dosyalar:
- `backend/src/services/chat_store.py`
- `backend/src/services/long_memory.py`
- `backend/src/services/memory_summarizer.py`

Seviyeler:
1. Session chat store: ham mesajlar (`.ayex/chats/sessions/*.jsonl`)
2. Long memory: profile + conversation/event jsonl
3. Memory summaries: LLM ozetleri + anahtar kelime tabanli geri cagirma
4. Retry queue: memory summary basarisizsa kalici kuyruk ve exponential backoff

## 8) Guvenlik Modeli

1. JWT auth: `AYEX_USER/AYEX_PASS` ile login, bearer token zorunlu route'lar
2. Auth middleware korumasi: `/chat`, `/action`, `/events`, `/event`, `/sessions`, `/profile`, `/usage`, `/intel`, `/audio`, `/voice`, `/tts`
3. Ingest ikinci katman token (opsiyonel)
4. Ingest rate limit (source+client bazli)
5. Tool policy:
- allowlist
- private/local URL bloklama
- timeout
- output truncation

## 9) Observability Standardi

### 9.1 Request-level telemetry

Dosya: `backend/src/middleware/request_metrics.py`

Her request icin:
- request_id (header'dan veya uretilen)
- method/path/status
- latency_ms
- user_id (varsa)

Response header:
- `x-request-id`
- `x-response-time-ms`

### 9.2 Structured event log helper

Dosya: `backend/src/utils/logging.py`

`log_event(logger, event, **fields)` ile standard format:
- `OBS event=<name> key=value ...`

Kullanildigi kritik yerler:
- bootstrap baslangic/hazir
- chat baslangic/sonuc
- events ingest reject/store
- request middleware

### 9.3 Runtime saglik endpoint'i

Dosya: `backend/src/routes/health.py`

`GET /health/ready` cikarimi:
- openai/anthropic config durumu
- intel event count
- memory retry queue size
- gunluk cost guard usage
- secili model adlari

## 10) Deploy Standardi

1. Tek start komutu: `python run_server.py`
2. Lokal script: `run_mvp.sh`
3. Runtime config dogrulama: `scripts/runtime_check.py`
4. Render blueprint: `render.yaml` (aynı env adlari)
5. CI: `.github/workflows/backend-ci.yml` (`py_compile + ruff + pytest`)

## 11) Konfigürasyon Referansi

Zorunlu:
- `OPENAI_API_KEY` (veya legacy fallback `AYEX_API_KEY`)

Model routing:
- `AYEX_CHAT_MODEL`
- `AYEX_REASONING_MODEL`
- `AYEX_POWER_MODEL`
- `AYEX_FAST_MODEL`
- `ANTHROPIC_API_KEY` (opsiyonel)

Model budget/cache:
- `AYEX_MODEL_MAX_OUTPUT_TOKENS`
- `AYEX_MODEL_CONTEXT_TURNS`
- `AYEX_MODEL_CACHE_TTL_SEC`
- `AYEX_MODEL_CACHE_SIZE`

Intel budget/ingest:
- `AYEX_INTEL_PROMPT_MAX_EVENTS`
- `AYEX_INTEL_PROMPT_MAX_CHARS`
- `AYEX_INTEL_INGEST_TOKEN`
- `AYEX_INTEL_INGEST_RPM`

Operasyonel:
- `AYEX_LOG_LEVEL`
- `AYEX_WEB_MVP_ONLY`
- `AYEX_DATA_DIR`
- `AYEX_PROFILE_PATH`
- `AYEX_CHAT_DIR`
- `AYEX_DAILY_REQUEST_LIMIT`
- `AYEX_DAILY_INPUT_CHAR_LIMIT`
- `AYEX_HOST`, `AYEX_PORT`

Ses:
- `AYEX_AUDIO_ENGINE_DEFAULT`
- `AYEX_STT_MODEL`
- `AYEX_TTS_MODEL`
- `AYEX_DEFAULT_VOICE`

## 12) API Referans

Auth gerektirmeyen endpointler:
- `POST /auth/login`
- `GET /health`
- `GET /health/ready`

Auth gerektiren endpointler:
- `POST /chat`
- `POST /action`
- `GET /profile`
- `PATCH /profile`
- `GET /sessions`
- `POST /sessions`
- `GET /sessions/{session_id}/messages`
- `DELETE /sessions/{session_id}`
- `GET /usage`
- `GET /intel`
- `GET /events/latest`
- `POST /events/ingest`

`AYEX_WEB_MVP_ONLY=false` ise ek endpointler:
- `POST /audio`
- `POST /voice/turn`
- `POST /tts`
- `POST /event`

## 13) Dosya Yapisi (Guncel)

### 13.1 Root

- `.env.example`: tum env degiskenleri icin baseline
- `run_mvp.sh`: local runtime bootstrap + config check
- `run_server.py`: uvicorn entrypoint
- `render.yaml`: Render deploy blueprint
- `requirements.txt`: backend bagimliliklari
- `.github/workflows/backend-ci.yml`: CI
- `scripts/runtime_check.py`: runtime env validation

### 13.2 Backend (`backend/src`)

#### Core

- `index.py`: app bootstrap, middleware ve router kayitlari
- `schemas.py`: request/response modelleri

#### Config

- `config/env.py`: tum ayarlarin load ve normalize edilmesi

#### Middleware

- `middleware/auth_middleware.py`: route bazli JWT enforcement
- `middleware/request_metrics.py`: request telemetry + correlation header

#### Routes

- `routes/auth.py`: login/token endpoint'i
- `routes/chat.py`: ana sohbet endpoint'i ve intel-first prompt olusturma
- `routes/action.py`: intent/tool/style destekli aksiyon endpoint'i
- `routes/events.py`: intel ingest ve latest event endpointleri
- `routes/intel.py`: daily brief
- `routes/history.py`: session/message CRUD
- `routes/profile.py`: profile read/update
- `routes/usage.py`: daily guard usage
- `routes/health.py`: basic + ready health
- `routes/audio.py`: STT->LLM->TTS ses turu
- `routes/tts.py`: text-to-speech endpoint'i
- `routes/event.py`: legacy placeholder event endpoint'i
- `routes/web.py`: legacy jarvis-style html panel
- `routes/deps.py`: service dependency resolver

#### Services

- `services/container.py`: tum servislerin composition root'u
- `services/model_service.py`: provider secimi + cache + token budget
- `services/model_router.py`: route/model secim kurallari
- `services/openai_client.py`: OpenAI Responses API wrapper
- `services/anthropic_client.py`: Anthropic SDK wrapper
- `services/chat_store.py`: session/message disk kaliciligi
- `services/long_memory.py`: uzun donem memory json/jsonl
- `services/memory_summarizer.py`: summary + retry queue
- `services/cost_guard.py`: gunluk request/char limiti (lock-safe, atomic)
- `services/tool_router.py`: tool policy/timeout/truncation
- `services/intent_router.py`: action intent siniflandirma
- `services/response_style.py`: brief/normal/deep stil secimi
- `services/response_orchestrator.py`: audio turn orchestration
- `services/stt_service.py`: speech-to-text
- `services/tts_service.py`: text-to-speech
- `services/voice_response.py`: voice-side compatibility logic
- `services/profile_service.py`: profile CRUD
- `services/auth_service.py`: credential + JWT
- `services/agent_mode.py`: plan + tool + final synthesis
- `services/agent_registry.py`: ayex_core agent cache
- `services/http_utils.py`: HTTP helper fonksiyonlari

#### Intel

- `intel/event_model.py`: IntelEvent dataclass
- `intel/intel_service.py`: validate, score, brief, context logic
- `intel/intel_store.py`: aktif event store + persist + restore
- `intel/intel_archive.py`: gunluk archive okuma/yazma

#### Tools

- `tools/registry.py`: tool kayit/dispatch
- `tools/base.py`: tool protocol ve execution modelleri
- `tools/search_tool.py`: web search
- `tools/fetch_url_tool.py`: URL content fetch
- `tools/market_tool.py`: canli market fetch (chat'te opsiyonel)

#### Utils

- `utils/logging.py`: logger ve structured log helper

### 13.3 Frontend (`frontend/src`)

- `main.jsx`: app entry
- `App.jsx`: root composition
- `pages/SystemPage.jsx`: ana sistem ekrani
- `components/ChatPanel.jsx`: chat UI + API baglantisi
- `components/StatusPanel.jsx`: model/latency/source gosterimi
- `components/MessageBubble.jsx`: mesaj karti
- `components/TypingDots.jsx`: typing indicator
- `components/HeroSection.jsx`: ust panel
- `components/BackgroundFX.jsx`: arkaplan efektleri
- `components/SignatureLogo.jsx`: marka imzasi
- `styles/index.css`: tum stil katmani

### 13.4 Legacy katman (`src/`)

- `src/ayex_api/server.py`: compatibility wrapper
- `src/ayex_core/*`: eski agent/core katmani (bazı servisler halen buradan sinif kullanir)

## 14) Veri Dosyalari (runtime)

`AYEX_DATA_DIR` altinda:
- `profile.json`
- `chats/sessions.json`
- `chats/sessions/<session_id>.jsonl`
- `intel_events.json`
- `archive/<YYYY-MM-DD>.json`
- `memory_summaries.json`
- `memory_summary_retry.json`
- `usage-daily.json`
- `memory_<user>.json`
- `memory_conversations_<user>.jsonl`
- `memory_events_<user>.jsonl`

## 15) Operasyon Notlari

1. Uretimde `AYEX_INTEL_INGEST_TOKEN` set ederek ingest endpointini ikinci katmanda koru.
2. `AYEX_INTEL_PROMPT_MAX_CHARS` cok dusuk olursa modelin intel kapsami azalir.
3. `AYEX_DAILY_REQUEST_LIMIT` ve `AYEX_DAILY_INPUT_CHAR_LIMIT` maliyet kontrolunun temelidir.
4. `/health/ready` endpointini deploy smoke-check ve uptime monitor'e bagla.
5. CI fail oldugunda merge yapma; py_compile + ruff + pytest temiz kalmali.

## 16) Durum

Bu repo su anda OpenClaw bridge kullanmadan, dogrudan provider SDK'lari ile calisan AYEX-IA runtime'ini temsil eder.

## 17) Core Docs

Omurga ve uygulama sirasi icin once su dosyalari oku:
- `VISION.md`
- `CORE_IDENTITY.md`
- `ARCHITECTURE.md`
- `PROJECT_STATE.md`
- `PHASES.md`
- `REPO_STRUCTURE.md`
- `IMPLEMENTATION_PLAN.md`
