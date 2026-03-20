from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.src.intel.intel_service import get_intel_summary
from backend.src.routes.deps import get_services
from backend.src.schemas import ChatRequest, ChatResponse
from backend.src.services.container import BackendServices
from backend.src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def get_latest_intel(services: BackendServices, *, user_id: str = "default") -> str:
    try:
        text = get_intel_summary(services.intel, user_id=user_id, max_chars=1400)
        if not text:
            logger.info("INTEL_FETCH_FAIL reason=empty_intel_summary")
            return ""
        logger.info("INTEL_FETCH_SUCCESS chars=%s", len(text))
        return text
    except Exception as exc:
        logger.info("INTEL_FETCH_FAIL error=%s", exc)
        return ""


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request, services: BackendServices = Depends(get_services)) -> ChatResponse:
    user_id = str(getattr(request.state, "user_id", "default"))
    ai_source = "openclaw" if services.settings.openclaw_enabled else "openai_direct"
    text = (payload.text or "").strip()
    if not text:
        return ChatResponse(reply="Bos mesaj gonderilemez.", session_id=payload.session_id or "", metrics={"ok": False})

    guard = services.cost_guard.check_and_track(text)
    if not guard.ok:
        return ChatResponse(
            reply=guard.reason,
            session_id=payload.session_id or "",
            metrics={"source": "guard", "ok": False, "usage": guard.usage or {}},
        )

    session = services.chat_store.ensure_session(payload.session_id, title_hint=text)
    dedup = services.chat_store.recent_assistant_for_duplicate(
        session.id,
        user_text=text,
        max_age_sec=services.settings.openclaw_cache_ttl_sec,
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
        return ChatResponse(
            reply=reply,
            session_id=session.id,
            metrics={
                "source": ai_source,
                "ok": prev_ok,
                "latency_ms": 0,
                "cache_hit": True,
                "memory_hits": 0,
                "used_model": prev_metrics.get("used_model", ""),
                "model_locked": bool(prev_metrics.get("model_locked", False)),
            },
        )

    history = services.chat_store.model_context(session.id, turns=services.settings.openclaw_context_turns)
    profile_data = services.profile.load()
    style_decision = services.style.detect(text, profile_style=str(profile_data.get("response_style") or ""))
    intent = services.intents.route(text)
    memory_context = services.chat_store.recall_context_text(
        query=text,
        exclude_session_id=session.id,
        limit=4,
    )
    long_memory_ctx = services.long_memory.build_context(query=text, limit=4, user_id=user_id)
    long_memory_text = long_memory_ctx.as_text()
    intel_data = get_latest_intel(services, user_id=user_id)
    memory_hits = 0 if not memory_context else max(1, memory_context.count("\n"))
    if long_memory_text:
        memory_hits += len(long_memory_ctx.conversation_hits) + len(long_memory_ctx.event_hits)
    if memory_hits > 0:
        logger.info("MEMORY_USED route=chat hits=%s", memory_hits)

    tool_result = services.tools.route_and_run(intent=intent.category, text=text)
    tool_context = tool_result.evidence_text()
    if tool_result.has_data:
        services.long_memory.append_event(
            event_type=f"tool:{tool_result.selected_tool or intent.category}",
            payload={"query": text, "evidence": tool_context[:3000]},
            source="tool_router",
            user_id=user_id,
        )

    merged_memory = "\n\n".join([x for x in [memory_context, long_memory_text] if x.strip()])
    model_input = text
    if tool_context:
        model_input = f"Kullanici sorusu: {text}\n\nTool kaniti:\n{tool_context}"
    intel_block = intel_data if intel_data else ""
    intel_system_prompt = (
        "You are Ayex-IA, a private intelligence system.\n\n"
        "Use the following real-time intelligence data to answer:\n\n"
        f"{intel_block}\n\n"
        "Rules:\n"
        "- You MUST synthesize insights, not list facts.\n"
        "- You MUST explain WHY the events matter.\n"
        "- You MUST connect events when there is a meaningful relationship.\n"
        "- You MUST infer plausible outcomes (near-term and second-order effects).\n"
        "- You MUST avoid generic statements (e.g., 'volatility exists') unless qualified with concrete implications.\n"
        "- If intel data exists, you MUST reference it explicitly in your analysis.\n"
        "- Do not say you lack real-time access.\n"
        "- Keep the tone analytical, decisive, non-generic, and free of filler text.\n\n"
        "Response format (always follow):\n"
        "1. Key Insight (1-2 sentences)\n"
        "2. Why It Matters\n"
        "3. Risk or Opportunity\n"
        "4. What to Watch\n"
    )
    profile_context_for_model = f"{services.profile.prompt_context()}\n\n{intel_system_prompt}"

    if intent.category == "agent_task":
        agent_res = services.agent_mode.run(
            text=text,
            workspace=payload.workspace,
            model=payload.model,
            profile_context=profile_context_for_model,
            memory_context=merged_memory,
            response_style=style_decision.style,
        )
        result = agent_res.final
    else:
        result = services.openclaw.run_action(
            model_input,
            workspace=payload.workspace,
            model=payload.model,
            history=history,
            profile_context=profile_context_for_model,
            memory_context=merged_memory,
            response_style=style_decision.style,
            route_name="chat",
        )

    reply = result.text if result.text else "Model yaniti alinamadi. Lutfen tekrar dene."

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
            "memory_hits": memory_hits,
            "used_model": result.used_model or "",
            "model_locked": result.model_locked,
            "response_style": style_decision.style,
            "intent": intent.category,
            "tool": tool_result.selected_tool,
        },
    )
    services.long_memory.sync_profile(profile_data, user_id=user_id)
    services.long_memory.append_conversation(
        session_id=session.id,
        user_text=text,
        assistant_text=reply,
        intent=intent.category,
        style=style_decision.style,
        user_id=user_id,
    )

    return ChatResponse(
        reply=reply,
        session_id=session.id,
        metrics={
            "source": result.source or ai_source,
            "ok": result.ok,
            "latency_ms": result.latency_ms,
            "cache_hit": result.cache_hit,
            "token_budget": result.token_budget,
            "context_messages": result.context_messages,
            "memory_hits": memory_hits,
            "used_model": result.used_model or "",
            "model_locked": result.model_locked,
            "response_style": style_decision.style,
            "intent": intent.category,
            "tool": tool_result.selected_tool,
        },
    )
