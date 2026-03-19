from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.src.routes.deps import get_services
from backend.src.schemas import ActionRequest, ActionResponse
from backend.src.services.container import BackendServices

router = APIRouter()


def _compact_raw(raw: dict) -> dict:
    if not raw:
        return {}
    if "error" in raw:
        return {"error": raw.get("error"), "mode": raw.get("mode")}
    compact = {
        "id": raw.get("id"),
        "model": raw.get("model"),
    }
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            compact["finish_reason"] = first.get("finish_reason")
    return {k: v for k, v in compact.items() if v is not None}


@router.post("/action", response_model=ActionResponse)
def action(payload: ActionRequest, services: BackendServices = Depends(get_services)) -> ActionResponse:
    text = (payload.text or "").strip()
    if not text:
        return ActionResponse(
            status="error",
            source="openclaw",
            reply="Bos mesaj gonderilemez.",
            session_id=payload.session_id or "",
            metrics={"ok": False},
            raw={},
        )

    guard = services.cost_guard.check_and_track(text)
    if not guard.ok:
        return ActionResponse(
            status="error",
            source="guard",
            reply=guard.reason,
            session_id=payload.session_id or "",
            metrics={"ok": False, "guard": True, "usage": guard.usage or {}},
            raw={},
        )

    session = services.chat_store.ensure_session(payload.session_id, title_hint=text)
    dedup = services.chat_store.recent_assistant_for_duplicate(
        session.id,
        user_text=text,
        max_age_sec=services.settings.openclaw_cache_ttl_sec,
    )
    if dedup is not None:
        reply = str(dedup.get("text") or "").strip() or "OpenClaw yanit uretemedi."
        prev_metrics = dedup.get("metrics") or {}
        prev_ok = bool(prev_metrics.get("ok", True))
        services.chat_store.append_message(session.id, role="user", text=text, source="user")
        services.chat_store.append_message(
            session.id,
            role="assistant",
            text=reply,
            source="openclaw",
            latency_ms=0,
            metrics={"cache_hit": True, "duplicate": True, "ok": prev_ok},
        )
        return ActionResponse(
            status="ok" if prev_ok else "error",
            source="openclaw",
            reply=reply,
            session_id=session.id,
            metrics={
                "ok": prev_ok,
                "latency_ms": 0,
                "cache_hit": True,
                "token_budget": prev_metrics.get("token_budget"),
                "context_messages": prev_metrics.get("context_messages"),
                "memory_hits": prev_metrics.get("memory_hits", 0),
                "used_model": prev_metrics.get("used_model", services.settings.openclaw_model),
                "model_locked": services.settings.openclaw_force_model,
            },
            raw={},
        )

    history = services.chat_store.model_context(session.id, turns=services.settings.openclaw_context_turns)
    profile_context = services.profile.prompt_context() if payload.use_profile else None
    memory_context = services.chat_store.recall_context_text(
        query=text,
        exclude_session_id=session.id,
        limit=4,
    )
    memory_hits = 0 if not memory_context else max(1, memory_context.count("\n"))

    result = services.openclaw.run_action(
        text,
        workspace=payload.workspace,
        model=payload.model,
        history=history,
        profile_context=profile_context,
        memory_context=memory_context,
    )

    reply = result.text if result.text else "OpenClaw baglanti hatasi."

    services.chat_store.append_message(session.id, role="user", text=text, source="user")
    services.chat_store.append_message(
        session.id,
        role="assistant",
        text=reply,
        source="openclaw",
        latency_ms=result.latency_ms,
        metrics={
            "cache_hit": result.cache_hit,
            "token_budget": result.token_budget,
            "context_messages": result.context_messages,
            "ok": result.ok,
            "memory_hits": memory_hits,
            "used_model": result.used_model or services.settings.openclaw_model,
            "model_locked": services.settings.openclaw_force_model,
        },
    )

    return ActionResponse(
        status="ok" if result.ok else "error",
        source="openclaw",
        reply=reply,
        session_id=session.id,
        metrics={
            "ok": result.ok,
            "latency_ms": result.latency_ms,
            "cache_hit": result.cache_hit,
            "token_budget": result.token_budget,
            "context_messages": result.context_messages,
            "memory_hits": memory_hits,
            "used_model": result.used_model or services.settings.openclaw_model,
            "model_locked": services.settings.openclaw_force_model,
        },
        raw=_compact_raw(result.raw),
    )
