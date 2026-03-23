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
export AYEX_MODEL="${AYEX_MODEL:-claude-haiku-4.5}"
export AYEX_CHAT_MODEL="${AYEX_CHAT_MODEL:-claude-haiku-4.5}"
export AYEX_REASONING_MODEL="${AYEX_REASONING_MODEL:-claude-sonnet-4.6}"
export AYEX_POWER_MODEL="${AYEX_POWER_MODEL:-gpt-5}"
export AYEX_FAST_MODEL="${AYEX_FAST_MODEL:-gpt-4o-mini}"
export AYEX_MODEL_MAX_OUTPUT_TOKENS="${AYEX_MODEL_MAX_OUTPUT_TOKENS:-320}"
export AYEX_MODEL_CONTEXT_TURNS="${AYEX_MODEL_CONTEXT_TURNS:-6}"
export AYEX_MODEL_CACHE_TTL_SEC="${AYEX_MODEL_CACHE_TTL_SEC:-45}"
export AYEX_MODEL_CACHE_SIZE="${AYEX_MODEL_CACHE_SIZE:-128}"
export AYEX_INTEL_PROMPT_MAX_EVENTS="${AYEX_INTEL_PROMPT_MAX_EVENTS:-20}"
export AYEX_INTEL_PROMPT_MAX_CHARS="${AYEX_INTEL_PROMPT_MAX_CHARS:-4200}"
export AYEX_INTEL_INGEST_RPM="${AYEX_INTEL_INGEST_RPM:-120}"
export AYEX_INTEL_INGEST_TOKEN="${AYEX_INTEL_INGEST_TOKEN:-}"
export AYEX_DATA_DIR="${AYEX_DATA_DIR:-.ayex}"
export AYEX_PROFILE_PATH="${AYEX_PROFILE_PATH:-.ayex/profile.json}"
export AYEX_CHAT_DIR="${AYEX_CHAT_DIR:-.ayex/chats}"
export AYEX_DAILY_REQUEST_LIMIT="${AYEX_DAILY_REQUEST_LIMIT:-350}"
export AYEX_DAILY_INPUT_CHAR_LIMIT="${AYEX_DAILY_INPUT_CHAR_LIMIT:-120000}"
export AYEX_LOG_LEVEL="${AYEX_LOG_LEVEL:-INFO}"

if [[ -z "${OPENAI_API_KEY:-}" && -z "${AYEX_API_KEY:-}" ]]; then
  echo "Hata: OPENAI_API_KEY (veya AYEX_API_KEY legacy) tanimli degil."
  exit 1
fi

echo "[MVP] Dogrudan model servis modu aktif (OpenAI + Anthropic)."
echo "[MVP] Backend baslatiliyor: http://127.0.0.1:${AYEX_PORT:-8000}"

if [[ -x "${ROOT_DIR}/scripts/runtime_check.py" ]]; then
  echo "[MVP] Runtime config dogrulaniyor..."
  "${ROOT_DIR}/scripts/runtime_check.py" || {
    echo "Hata: runtime config check basarisiz."
    exit 1
  }
fi

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
