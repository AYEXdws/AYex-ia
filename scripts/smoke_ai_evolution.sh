#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "[smoke] health"
curl -fsS "${BASE_URL}/health"; echo

echo "[smoke] chat (brief+market intent)"
curl -fsS -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"text":"kısa anlat bugün piyasada ne oldu"}'; echo

echo "[smoke] action (agent_task intent)"
curl -fsS -X POST "${BASE_URL}/action" \
  -H "Content-Type: application/json" \
  -d '{"text":"bitcoin ve ethereumu karşılaştır, kısa rapor hazırla"}'; echo

echo "[smoke] event ingest"
curl -fsS -X POST "${BASE_URL}/events/ingest" \
  -H "Content-Type: application/json" \
  -d '{"type":"market_signal","payload":{"asset":"ETH","move":"+1.3%"}}'; echo

echo "[smoke] done"
