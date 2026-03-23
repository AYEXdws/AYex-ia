#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys


def _bool(v: str | None) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    openai_key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("AYEX_API_KEY") or "").strip()
    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()

    errors: list[str] = []
    if not openai_key:
        errors.append("OPENAI_API_KEY (veya AYEX_API_KEY) gerekli")

    prompt_events = int(os.environ.get("AYEX_INTEL_PROMPT_MAX_EVENTS", "20") or 20)
    prompt_chars = int(os.environ.get("AYEX_INTEL_PROMPT_MAX_CHARS", "4200") or 4200)
    if prompt_events < 4 or prompt_events > 40:
        errors.append("AYEX_INTEL_PROMPT_MAX_EVENTS 4..40 araliginda olmali")
    if prompt_chars < 1200 or prompt_chars > 20000:
        errors.append("AYEX_INTEL_PROMPT_MAX_CHARS 1200..20000 araliginda olmali")

    snapshot = {
        "openai_configured": bool(openai_key),
        "anthropic_configured": bool(anthropic_key),
        "chat_model": os.environ.get("AYEX_CHAT_MODEL", "claude-haiku-4.5"),
        "reasoning_model": os.environ.get("AYEX_REASONING_MODEL", "claude-sonnet-4.6"),
        "power_model": os.environ.get("AYEX_POWER_MODEL", "gpt-5"),
        "fast_model": os.environ.get("AYEX_FAST_MODEL", "gpt-4o-mini"),
        "web_mvp_only": _bool(os.environ.get("AYEX_WEB_MVP_ONLY", "true")),
        "intel_prompt_max_events": prompt_events,
        "intel_prompt_max_chars": prompt_chars,
        "intel_ingest_rpm": int(os.environ.get("AYEX_INTEL_INGEST_RPM", "120") or 120),
        "log_level": os.environ.get("AYEX_LOG_LEVEL", "INFO"),
    }

    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
