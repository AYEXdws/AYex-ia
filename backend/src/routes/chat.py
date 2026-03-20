from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.src.intel.intel_service import build_intel_context
from backend.src.routes.deps import get_services
from backend.src.schemas import ChatRequest, ChatResponse
from backend.src.services.container import BackendServices
from backend.src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def get_latest_intel(services: BackendServices, *, user_id: str = "default") -> dict[str, Any]:
    try:
        intel_context = build_intel_context(services.intel, user_id=user_id)
        if not isinstance(intel_context, dict):
            logger.info("INTEL_FETCH_FAIL reason=invalid_intel_context")
            return {}
        logger.info(
            "INTEL_CONTEXT_BUILT events=%s signals=%s confidence=%.3f",
            len(intel_context.get("key_events") or []),
            len(intel_context.get("signals") or []),
            float(intel_context.get("confidence") or 0.0),
        )
        logger.info("INTEL_FETCH_SUCCESS source=internal")
        return intel_context
    except Exception as exc:
        logger.info("INTEL_FETCH_FAIL error=%s", exc)
        return {}


def format_intel_for_prompt(intel_context: dict[str, Any]) -> str:
    key_events = intel_context.get("key_events") or []
    signals = intel_context.get("signals") or []
    summary = str(intel_context.get("summary") or "").strip()
    confidence = float(intel_context.get("confidence") or 0.0)

    event_lines = []
    for idx, item in enumerate(key_events[:5], start=1):
        title = str(item.get("title") or "").strip()
        cat = str(item.get("category") or "").strip()
        score = float(item.get("score") or 0.0)
        src = str(item.get("source") or "").strip()
        ev_summary = str(item.get("summary") or "").strip()
        event_lines.append(f"{idx}) {title} | cat={cat} | score={score:.2f} | src={src} | summary={ev_summary}")

    signal_lines = [f"- {s}" for s in signals[:8]]
    if not event_lines:
        event_lines = ["No high-priority events."]
    if not signal_lines:
        signal_lines = ["- No extracted signal."]

    return (
        "INTELLIGENCE DATA:\n"
        "- Key Events:\n"
        + "\n".join(event_lines)
        + "\n- Signals:\n"
        + "\n".join(signal_lines)
        + "\n- Summary:\n"
        + (summary or "No intel summary.")
        + f"\n- Confidence: {confidence:.2f}"
    )[:2200]


def extract_user_focus(services: BackendServices, session_id: str, current_text: str) -> str:
    recent = services.chat_store.messages(session_id, limit=14)
    user_texts = [str(m.get("text") or "") for m in recent if str(m.get("role") or "") == "user"][-3:]
    user_texts.append(current_text)
    bag = " ".join(user_texts).lower()
    labels: list[str] = []
    if any(k in bag for k in ("btc", "eth", "kripto", "crypto", "coin", "altcoin")):
        labels.append("crypto")
    if any(k in bag for k in ("security", "guvenlik", "breach", "sizinti", "hack")):
        labels.append("security")
    if any(k in bag for k in ("global", "jeopolitik", "fed", "makro", "risk", "regulation")):
        labels.append("global risk")
    if not labels:
        labels.append("general intelligence")
    return " / ".join(labels[:3])


def validate_response(text: str) -> bool:
    low = str(text or "").lower()
    if not low.strip():
        return False
    banned_generic = (
        "generally",
        "in general",
        "volatility exists",
        "it depends",
        "could be many reasons",
        "zor söylemek",
        "genel olarak",
    )
    if any(p in low for p in banned_generic):
        return False
    required_sections = ("key insight", "why it matters", "risk", "what to watch")
    if sum(1 for s in required_sections if s in low) < 3:
        return False
    causal_markers = ("because", "leads to", "implies", "drives", "therefore", "bu nedenle", "tetikler")
    if not any(m in low for m in causal_markers):
        return False
    return True


def did_use_intel(response: str, intel_context: dict[str, Any]) -> bool:
    low = str(response or "").lower()
    if not low.strip():
        return False
    events = intel_context.get("key_events") or []
    refs = 0
    for item in events[:5]:
        title = str(item.get("title") or "").strip().lower()
        if title and (title in low or any(tok in low for tok in re.findall(r"[a-z0-9]{4,}", title)[:3])):
            refs += 1
    if refs > 0:
        return True
    for sig in intel_context.get("signals") or []:
        part = str(sig or "").split(":", 1)[-1].strip().lower()
        if part and part in low:
            return True
    return False


def score_response(response: str) -> dict[str, float]:
    low = str(response or "").lower()
    words = [w for w in re.findall(r"[a-zA-Z0-9_]+", low) if w]
    length_score = min(1.0, len(words) / 220.0)
    causal_score = 1.0 if any(x in low for x in ("because", "leads to", "implies", "therefore", "bu nedenle")) else 0.35
    intel_score = 1.0 if any(x in low for x in ("key insight", "what to watch", "signals", "confidence")) else 0.4
    return {
        "depth_score": round((length_score * 0.55) + (causal_score * 0.45), 4),
        "relevance_score": round((causal_score * 0.6) + (intel_score * 0.4), 4),
        "intel_usage_score": round(intel_score, 4),
    }


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
    intel_context = get_latest_intel(services, user_id=user_id)
    intel_data = format_intel_for_prompt(intel_context) if intel_context else ""
    user_focus = extract_user_focus(services, session.id, text)
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
    intel_block = intel_data if intel_data else "INTELLIGENCE DATA:\n- Key Events:\nNo high-priority events."
    intel_system_prompt = (
        "You are Ayex-IA, a private intelligence system.\n\n"
        "Core Behavior:\n"
        "- You are NOT an assistant. You are an intelligence analyst.\n"
        "- You do NOT list information. You extract meaning.\n"
        "- You do NOT repeat intel. You transform it into insight.\n\n"
        "Use the following real-time intelligence data:\n\n"
        f"{intel_block}\n\n"
        f"User focus: {user_focus}\n\n"
        "Rules:\n"
        "- You MUST synthesize insights, not list facts.\n"
        "- You MUST explicitly reference relevant intel data in your reasoning.\n"
        "- You MUST explain WHY the events matter.\n"
        "- You MUST connect events when there is a meaningful relationship.\n"
        "- You MUST infer plausible outcomes (near-term and second-order effects).\n"
        "- You MUST take a position; avoid neutral and vague language.\n"
        "- You MUST avoid generic statements unless tied to concrete implications.\n"
        "- If intel is weak, explain the limitation analytically.\n"
        "- Do not say you lack real-time access.\n"
        "- Tone: analytical, causal, concise-dense, no filler.\n\n"
        "Response format (always follow):\n"
        "1. Key Insight (1-2 sharp sentences)\n"
        "2. Why It Matters\n"
        "3. Risk / Opportunity\n"
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
    used_intel = did_use_intel(reply, intel_context)
    if used_intel:
        logger.info("INTEL_USED_TRUE")
    else:
        logger.info("INTEL_USED_FALSE")
    is_valid = validate_response(reply)
    if not is_valid or not used_intel:
        logger.info("RESPONSE_REJECTED_GENERIC reason=%s", "intel_missing" if not used_intel else "generic_or_noncausal")
        retry_profile_context = (
            f"{profile_context_for_model}\n\n"
            "Your previous response ignored requirements. Regenerate once.\n"
            "You MUST use intel data explicitly, include causal links, and follow the exact 4-section format."
        )
        logger.info("RESPONSE_REGENERATED")
        retry_result = services.openclaw.run_action(
            model_input,
            workspace=payload.workspace,
            model=payload.model,
            history=history,
            profile_context=retry_profile_context,
            memory_context=merged_memory,
            response_style=style_decision.style,
            route_name="chat_regen",
        )
        retry_reply = (retry_result.text or "").strip()
        if retry_reply:
            reply = retry_reply
            result = retry_result
        used_intel = did_use_intel(reply, intel_context)
        logger.info("INTEL_USED_%s", "TRUE" if used_intel else "FALSE")
    response_scores = score_response(reply)

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
            "response_score": response_scores,
            "intel_used": used_intel,
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
            "response_score": response_scores,
            "intel_used": used_intel,
        },
    )
