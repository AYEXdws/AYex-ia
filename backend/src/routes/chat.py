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


def _normalize_text(text: str) -> str:
    low = (text or "").lower()
    table = str.maketrans(
        {
            "ç": "c",
            "ğ": "g",
            "ı": "i",
            "İ": "i",
            "ö": "o",
            "ş": "s",
            "ü": "u",
        }
    )
    return low.translate(table)


def _extract_tokens(text: str) -> set[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "your",
        "have",
        "will",
        "about",
        "olarak",
        "icin",
        "ve",
        "ile",
        "ama",
        "gibi",
        "daha",
        "cok",
        "kadar",
        "olan",
        "olanlar",
        "sadece",
        "genel",
        "bazi",
        "gore",
    }
    tokens = set(re.findall(r"[a-z0-9]{3,}", _normalize_text(text)))
    return {t for t in tokens if len(t) >= 4 and t not in stopwords}


def get_latest_intel(services: BackendServices, *, user_id: str = "default") -> dict[str, Any]:
    try:
        intel_context = build_intel_context(services.intel, user_id=user_id)
        if not isinstance(intel_context, dict):
            logger.info("INTEL_FETCH_FAIL reason=invalid_intel_context")
            return {}
        logger.info(
            "INTEL_CONTEXT_BUILT event_count=%s signal_count=%s confidence=%.3f time_window=%s",
            len(intel_context.get("key_events") or []),
            len(intel_context.get("signals") or []),
            float(intel_context.get("confidence") or 0.0),
            str(intel_context.get("recency_note") or "unknown"),
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
    recency_note = str(intel_context.get("recency_note") or "").strip()

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
        + (f"\n- Recency: {recency_note}" if recency_note else "")
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
    valid, _ = validate_response_detailed(text)
    return valid


def validate_response_detailed(text: str) -> tuple[bool, str]:
    low = _normalize_text(str(text or ""))
    if not low.strip():
        return False, "empty"
    banned_generic = (
        "generally",
        "in general",
        "volatility exists",
        "it depends",
        "could be many reasons",
        "zor soylemek",
        "genel olarak",
        "piyasa dalgali",
        "belirsizlik var",
    )
    if any(p in low for p in banned_generic):
        return False, "generic_phrase"

    section_patterns = {
        "insight": r"(?:^|\n)\s*(?:\d+[\).\s-]*)?(?:key\s*insight|temel\s*icgor[uü]|ana\s*icgor[uü])\b",
        "why": r"(?:^|\n)\s*(?:\d+[\).\s-]*)?(?:why\s*it\s*matters|neden\s*onemli|neden\s*kritik)\b",
        "risk": r"(?:^|\n)\s*(?:\d+[\).\s-]*)?(?:risk\s*(?:/|\||veya|-)?\s*(?:opportunity|firsat)|risk|firsat)\b",
        "watch": r"(?:^|\n)\s*(?:\d+[\).\s-]*)?(?:what\s*to\s*watch|izlenecekler|izlenmesi\s*gerekenler)\b",
    }
    section_hits = sum(1 for _, pat in section_patterns.items() if re.search(pat, low, flags=re.IGNORECASE))
    if section_hits < 3:
        return False, "section_missing"

    causal_markers = (
        "because",
        "leads to",
        "implies",
        "drives",
        "therefore",
        "bu nedenle",
        "tetikler",
        "sonucunda",
        "neden olur",
    )
    if not any(m in low for m in causal_markers):
        return False, "causal_missing"
    return True, "ok"


def did_use_intel(response: str, intel_context: dict[str, Any]) -> bool:
    used, _ = did_use_intel_detailed(response, intel_context)
    return used


def did_use_intel_detailed(response: str, intel_context: dict[str, Any]) -> tuple[bool, str]:
    low = _normalize_text(str(response or ""))
    if not low.strip():
        return False, "empty_response"
    response_tokens = _extract_tokens(low)
    if not response_tokens:
        return False, "low_token_density"

    events = intel_context.get("key_events") or []
    if not events:
        return False, "no_intel_events"

    title_hit = 0
    summary_overlap = 0
    category_hit = 0
    signal_hit = 0
    intel_token_bag: set[str] = set()

    for item in events[:5]:
        title = _normalize_text(str(item.get("title") or "").strip())
        title_tokens = _extract_tokens(title)
        intel_token_bag |= title_tokens
        if title and title in low:
            title_hit += 1
        elif len(response_tokens & title_tokens) >= 2:
            title_hit += 1

        summary = _normalize_text(str(item.get("summary") or ""))
        summary_tokens = _extract_tokens(summary)
        intel_token_bag |= summary_tokens
        if len(response_tokens & summary_tokens) >= 2:
            summary_overlap += 1

        category = _normalize_text(str(item.get("category") or "").strip())
        if category:
            cat_tokens = _extract_tokens(category) or {category}
            intel_token_bag |= cat_tokens
            if response_tokens & cat_tokens:
                category_hit += 1

    for sig in intel_context.get("signals") or []:
        sig_norm = _normalize_text(str(sig or ""))
        sig_tokens = _extract_tokens(sig_norm)
        intel_token_bag |= sig_tokens
        if sig_norm and sig_norm in low:
            signal_hit += 1
            continue
        if response_tokens & sig_tokens:
            signal_hit += 1

    concept_overlap = len(response_tokens & intel_token_bag)
    if title_hit >= 1 and concept_overlap >= 2:
        return True, "title_overlap"
    if signal_hit >= 1 and concept_overlap >= 2:
        return True, "signal_overlap"
    if category_hit >= 1 and summary_overlap >= 1 and concept_overlap >= 3:
        return True, "category_summary_overlap"
    return False, "insufficient_intel_reference"


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


def build_safe_fallback_response(intel_context: dict[str, Any], user_text: str) -> str:
    events = intel_context.get("key_events") or []
    signals = intel_context.get("signals") or []
    confidence = float(intel_context.get("confidence") or 0.0)

    if not events:
        return (
            "1. Key Insight\n"
            "Current signal density is low; available intelligence does not support a high-conviction directional call.\n\n"
            "2. Why It Matters\n"
            "Low-confidence conditions increase model risk because weak evidence can produce false certainty in decision making.\n\n"
            "3. What to Watch\n"
            "Watch for fresh high-score events, repeated anomaly signals, and confidence rising above 0.60 before taking aggressive action."
        )

    top = events[0]
    title = str(top.get("title") or "Top event")
    category = str(top.get("category") or "other")
    score = float(top.get("effective_score") or top.get("score") or 0.0)
    signal = str(signals[0] if signals else f"risk:{title}")
    user_focus_tokens = _extract_tokens(user_text)
    focus_text = " / ".join(sorted(list(user_focus_tokens))[:3]) if user_focus_tokens else "current user focus"

    return (
        "1. Key Insight\n"
        f"Primary signal is '{title}' ({category}) with effective score {score:.2f}; this currently dominates the intelligence stack.\n\n"
        "2. Why It Matters\n"
        f"The event aligns with '{signal}', which implies near-term pressure channels can propagate into {focus_text}; "
        f"confidence is {confidence:.2f}, so the signal is actionable but should be monitored for confirmation.\n\n"
        "3. What to Watch\n"
        "Track whether related signals cluster in the next cycle, whether risk-tagged events accelerate, and whether confidence trends up or down."
    )


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
    used_intel, intel_reason = did_use_intel_detailed(reply, intel_context)
    logger.info("INTEL_USED_%s reason=%s", "TRUE" if used_intel else "FALSE", intel_reason)
    is_valid, validation_reason = validate_response_detailed(reply)
    if not is_valid or not used_intel:
        reason_type = "intel_missing" if not used_intel else validation_reason
        logger.info("RESPONSE_REJECTED_GENERIC reason=%s", reason_type)
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
        used_intel, intel_reason = did_use_intel_detailed(reply, intel_context)
        is_valid, validation_reason = validate_response_detailed(reply)
        logger.info("INTEL_USED_%s reason=%s", "TRUE" if used_intel else "FALSE", intel_reason)
        if not is_valid or not used_intel:
            logger.info("RESPONSE_REJECTED_AFTER_REGEN reason=%s", validation_reason if not is_valid else intel_reason)
            reply = build_safe_fallback_response(intel_context, text)
            logger.info("SAFE_FALLBACK_USED")
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
