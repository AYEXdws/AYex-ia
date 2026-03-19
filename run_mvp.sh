#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export AYEX_WEB_MVP_ONLY="${AYEX_WEB_MVP_ONLY:-true}"
export OPENCLAW_ENABLED="${OPENCLAW_ENABLED:-true}"
export OPENCLAW_BASE_URL="${OPENCLAW_BASE_URL:-http://127.0.0.1:18789}"
export OPENCLAW_MODE="${OPENCLAW_MODE:-openai_chat_completions}"
export OPENCLAW_MODEL="${OPENCLAW_MODEL:-openai/gpt-4o-mini}"
export OPENCLAW_FORCE_MODEL="${OPENCLAW_FORCE_MODEL:-true}"
export OPENCLAW_MAX_OUTPUT_TOKENS="${OPENCLAW_MAX_OUTPUT_TOKENS:-80}"
export OPENCLAW_TIMEOUT_SEC="${OPENCLAW_TIMEOUT_SEC:-12}"
export OPENCLAW_CONTEXT_TURNS="${OPENCLAW_CONTEXT_TURNS:-6}"
export OPENCLAW_CACHE_TTL_SEC="${OPENCLAW_CACHE_TTL_SEC:-45}"
export OPENCLAW_CACHE_SIZE="${OPENCLAW_CACHE_SIZE:-128}"
export OPENCLAW_INSTRUCTIONS="${OPENCLAW_INSTRUCTIONS:-Her zaman Turkce cevap ver. Kisa, net ve dogal yaz. Basit sorularda 2-4 cumle kullan; analiz gereken durumda maddeli ve yapisal yanit ver.}"
export AYEX_DATA_DIR="${AYEX_DATA_DIR:-.ayex}"
export AYEX_PROFILE_PATH="${AYEX_PROFILE_PATH:-.ayex/profile.json}"
export AYEX_CHAT_DIR="${AYEX_CHAT_DIR:-.ayex/chats}"
export AYEX_DAILY_REQUEST_LIMIT="${AYEX_DAILY_REQUEST_LIMIT:-350}"
export AYEX_DAILY_INPUT_CHAR_LIMIT="${AYEX_DAILY_INPUT_CHAR_LIMIT:-120000}"

if [[ -z "${OPENAI_API_KEY:-}" && -z "${AYEX_API_KEY:-}" ]]; then
  echo "Hata: OPENAI_API_KEY (veya AYEX_API_KEY) tanimli degil."
  exit 1
fi

if [[ "${OPENCLAW_ENABLED}" == "true" ]]; then
  echo "[MVP] OpenClaw kontrol: ${OPENCLAW_BASE_URL}"
  if ! curl -fsS --max-time 3 "${OPENCLAW_BASE_URL}" >/dev/null 2>&1; then
    echo "Hata: OpenClaw gateway ulasilamiyor (${OPENCLAW_BASE_URL})."
    echo "OpenClaw servisini baslatip tekrar dene veya OPENCLAW_ENABLED=false kullan."
    exit 1
  fi
else
  echo "[MVP] OpenClaw devre disi: dogrudan OpenAI istemcisi kullanilacak."
fi

echo "[MVP] Backend baslatiliyor: http://127.0.0.1:${AYEX_PORT:-8000}"
PY_BIN="${ROOT_DIR}/.venv/bin/python"
PIP_BIN="${ROOT_DIR}/.venv/bin/pip"

if [[ ! -x "${PY_BIN}" ]]; then
  echo "Hata: .venv bulunamadi. Once sanal ortam olustur:"
  echo "python3 -m venv .venv"
  exit 1
fi

if ! "${PY_BIN}" -c "import uvicorn, fastapi, pydantic" >/dev/null 2>&1; then
  echo "[MVP] Eksik Python paketleri kuruluyor..."
  "${PIP_BIN}" install -r requirements.txt >/dev/null
fi

"${PY_BIN}" run_server.py
