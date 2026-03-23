from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready(services: BackendServices = Depends(get_services)) -> dict:
    openai_configured = bool((os.environ.get("OPENAI_API_KEY") or os.environ.get("AYEX_API_KEY") or "").strip())
    anthropic_configured = bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())
    event_count = len(services.intel.store.get_all_events())
    memory_retry_queue = services.memory.retry_queue_size()
    usage = services.cost_guard.usage_today()
    return {
        "status": "ok" if openai_configured else "degraded",
        "checks": {
            "openai_configured": openai_configured,
            "anthropic_configured": anthropic_configured,
            "events_available": event_count > 0,
        },
        "runtime": {
            "chat_model": services.settings.ayex_chat_model,
            "reasoning_model": services.settings.ayex_reasoning_model,
            "power_model": services.settings.ayex_power_model,
            "fast_model": services.settings.ayex_fast_model,
            "intel_event_count": event_count,
            "memory_retry_queue": memory_retry_queue,
            "daily_usage": usage,
        },
    }
