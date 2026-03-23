from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.src.routes.deps import get_services
from backend.src.schemas import ActionRequest, ActionResponse
from backend.src.services.container import BackendServices
from backend.src.services.market_decision import build_decision_prompt_block, build_market_decision, enforce_decision_reply
from backend.src.services.proactive_briefing import build_proactive_briefing
from backend.src.services.query_context import build_explainability_trace, build_query_context, collect_tool_evidence
from backend.src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


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
def action(payload: ActionRequest, request: Request, services: BackendServices = Depends(get_services)) -> ActionResponse:
    user_id = str(getattr(request.state, "user_id", "default"))
    ai_source = "model_direct"
    text = (payload.text or "").strip()
    if not text:
        return ActionResponse(
            status="error",
            source=ai_source,
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
        max_age_sec=services.settings.model_cache_ttl_sec,
    )
    if dedup is not None:
        reply = str(dedup.get("text") or "").strip() or "Model yaniti alinamadi. Lutfen tekrar dene."
        prev_metrics = dedup.get("metrics") or {}
        prev_ok = bool(prev_metrics.get("ok", True))
        services.chat_store.append_message(session.id, role="user", text=text, source="user")
        services.chat_store.append_message(
            session.id,
            role="assistant",
            text=reply,
            source=ai_source,
            latency_ms=0,
            metrics={"cache_hit": True, "duplicate": True, "ok": prev_ok},
        )
        return ActionResponse(
            status="ok" if prev_ok else "error",
            source=ai_source,
            reply=reply,
            session_id=session.id,
            metrics={
                "ok": prev_ok,
                "latency_ms": 0,
                "cache_hit": True,
                "token_budget": prev_metrics.get("token_budget"),
                "context_messages": prev_metrics.get("context_messages"),
                "memory_hits": prev_metrics.get("memory_hits", 0),
                "used_model": prev_metrics.get("used_model", ""),
                "model_locked": bool(prev_metrics.get("model_locked", False)),
            },
            raw={},
        )

    history = services.chat_store.model_context(session.id, turns=services.settings.model_context_turns)
    query_ctx = build_query_context(
        services,
        text=text,
        session_id=session.id,
        user_id=user_id,
        use_profile=payload.use_profile,
        max_intel_events=max(4, int(getattr(services.settings, "intel_prompt_max_events", 6) or 6)),
    )
    latest_events = []
    try:
        latest_events = list(getattr(services.intel, "get_latest_events")(limit=8) or [])
    except Exception:
        latest_events = []
    proactive_brief = build_proactive_briefing(services.intel, user_id=user_id, limit=6)
    decision = build_market_decision(
        text=text,
        intel_context=query_ctx.intel_context,
        latest_events=latest_events,
    ).as_dict()
    if query_ctx.memory_hits > 0:
        logger.info("MEMORY_USED route=action hits=%s", query_ctx.memory_hits)

    tool_result = collect_tool_evidence(services, intent_category=query_ctx.intent_category, text=text)
    tool_context = tool_result.text
    if tool_result.has_data:
        services.long_memory.append_event(
            event_type=f"tool:{tool_result.selected_tool or query_ctx.intent_category}",
            payload={"query": text, "evidence": tool_context[:3000]},
            source="tool_router",
            user_id=user_id,
        )

    decision_block = build_decision_prompt_block(decision)
    combined_profile_context = "\n\n".join(
        [
            part
            for part in (
                f"Yanit politikasi:\n{query_ctx.response_policy}",
                query_ctx.profile_context,
                f"Proaktif brief:\n{proactive_brief.get('summary')}" if proactive_brief.get("summary") else "",
                f"Karar notu:\n{decision_block}" if decision.get("active") else "",
                f"Sorguya ilgili intel:\n{query_ctx.intel_context_text}" if query_ctx.intel_context_text else "",
            )
            if str(part or "").strip()
        ]
    )
    model_input = text
    if decision.get("active"):
        model_input = f"Kullanici istegi: {text}\n\nKarar notu:\n{decision_block}"
    if tool_context:
        model_input = f"{model_input}\n\nTool kaniti:\n{tool_context}"

    if query_ctx.intent_category == "agent_task":
        agent_res = services.agent_mode.run(
            text=text,
            workspace=payload.workspace,
            model=payload.model,
            profile_context=combined_profile_context,
            memory_context=query_ctx.merged_memory,
            response_style=query_ctx.response_style,
        )
        result = agent_res.final
    else:
        result = services.model.run_action(
            model_input,
            workspace=payload.workspace,
            model=payload.model,
            history=history,
            profile_context=combined_profile_context,
            memory_context=query_ctx.merged_memory,
            response_style=query_ctx.response_style,
            route_name="action",
        )

    reply = result.text if result.text else "Model yaniti alinamadi. Lutfen tekrar dene."
    reply = enforce_decision_reply(decision=decision, reply=reply)
    explainability = build_explainability_trace(
        query_ctx=query_ctx,
        proactive_brief=proactive_brief,
        decision=decision,
        route="agent_task" if query_ctx.intent_category == "agent_task" else "action",
        model=str(getattr(result, "used_model", "") or payload.model or ""),
        tool=tool_result.selected_tool,
    )

    services.chat_store.append_message(session.id, role="user", text=text, source="user")
    services.chat_store.append_message(
        session.id,
        role="assistant",
        text=reply,
        source=result.source or ai_source,
        latency_ms=result.latency_ms,
        metrics={
            "cache_hit": result.cache_hit,
            "token_budget": result.token_budget,
            "context_messages": result.context_messages,
            "ok": result.ok,
            "memory_hits": query_ctx.memory_hits,
            "used_model": result.used_model or "",
            "model_locked": result.model_locked,
            "response_style": query_ctx.response_style,
            "intent": query_ctx.intent_category,
            "tool": tool_result.selected_tool,
            "decision": decision,
            "proactive_brief": proactive_brief,
            "explainability": explainability,
        },
    )
    services.long_memory.sync_profile(query_ctx.profile_data, user_id=user_id)
    services.long_memory.append_conversation(
        session_id=session.id,
        user_text=text,
        assistant_text=reply,
        intent=query_ctx.intent_category,
        style=query_ctx.response_style,
        user_id=user_id,
    )

    return ActionResponse(
        status="ok" if result.ok else "error",
        source=result.source or ai_source,
        reply=reply,
        session_id=session.id,
        metrics={
            "ok": result.ok,
            "latency_ms": result.latency_ms,
            "cache_hit": result.cache_hit,
            "token_budget": result.token_budget,
            "context_messages": result.context_messages,
            "memory_hits": query_ctx.memory_hits,
            "used_model": result.used_model or "",
            "model_locked": result.model_locked,
            "response_style": query_ctx.response_style,
            "intent": query_ctx.intent_category,
            "tool": tool_result.selected_tool,
            "decision": decision,
            "proactive_brief": proactive_brief,
            "explainability": explainability,
        },
        raw=_compact_raw(result.raw),
    )
