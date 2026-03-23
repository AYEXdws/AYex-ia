# Architecture Overview

Bu dokumanin amaci hizli referans vermektir. Ayrintili teknik harita icin kok dizindeki `README.md` kanonik kaynaktir.

## Runtime Entry Points

- Backend API: `python run_server.py`
- Local bootstrap: `./run_mvp.sh`
- Frontend build (Vite): `frontend/`
- ESP32 client: `esp32-client/`

## Core Stack

- FastAPI backend (`backend/src`)
- React frontend (`frontend/src`)
- Direct provider model gateway (OpenAI + Anthropic)
- Intel + memory + chat store kaliciligi (`.ayex`)

## Request Lifecycle (High Level)

1. Request middleware: metrics + auth
2. Route handler: guard + context toplama
3. Model call: `ModelService`
4. Persistence: `ChatStore` + `LongMemory`
5. Response + telemetry headers

## Canonical References

- Sistemin tam dosya haritasi: `README.md`, Bolum 13
- Chat akis detaylari: `README.md`, Bolum 4.1
- Deploy standardi: `README.md`, Bolum 10
- Observability standardi: `README.md`, Bolum 9
