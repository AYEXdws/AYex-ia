from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.src.intel.intel_service import build_intel_context, select_relevant_intel_context, summarize_intel_context
from backend.src.routes.deps import get_services
from backend.src.schemas import ChatRequest, ChatResponse
from backend.src.services.container import BackendServices
from backend.src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _normalize_text(text: str) -> str:
    low = (text or "").lower().replace("i̇", "i").replace("\u0307", "")
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


def _looks_turkish(text: str) -> bool:
    low = _normalize_text(text)
    turkish_markers = (
        " ve ",
        " bir ",
        " bu ",
        " neden ",
        " onemli ",
        " sonucunda ",
        " bu nedenle ",
        " kisa vadede ",
        " izlenmeli ",
        " firsat ",
    )
    english_markers = (
        " the ",
        " and ",
        " because ",
        " therefore ",
        " opportunity ",
        " watch ",
        " insight ",
        " in the ",
        " market ",
    )
    tr_hits = sum(1 for marker in turkish_markers if marker in f" {low} ")
    en_hits = sum(1 for marker in english_markers if marker in f" {low} ")
    return tr_hits >= 2 or en_hits <= 1


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


def format_intel_for_prompt(intel_context: dict[str, Any], *, relevant: bool = False) -> str:
    key_events = intel_context.get("key_events") or []
    signals = intel_context.get("signals") or []
    summary = str(intel_context.get("summary") or "").strip()
    confidence = float(intel_context.get("confidence") or 0.0)
    recency_note = str(intel_context.get("recency_note") or "").strip()
    query_focus = intel_context.get("query_focus") or {}
    focus_topics = query_focus.get("topics") or []
    focus_bias = query_focus.get("category_bias") or []
    focus_tokens = query_focus.get("tokens") or []
    focus_text = (
        f"konular={', '.join(focus_topics) if focus_topics else 'genel'} | "
        f"kategori_onceligi={', '.join(focus_bias) if focus_bias else 'yok'} | "
        f"ana_anahtarlar={', '.join([str(t) for t in focus_tokens[:8]]) if focus_tokens else 'yok'}"
    )

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
        event_lines = ["Yuksek oncelikli olay bulunamadi."]
    if not signal_lines:
        signal_lines = ["- Cikarilan sinyal yok."]

    header = "ILGILI ISTIHBARAT VERISI" if relevant else "ISTIHBARAT VERISI"
    return (
        "SORU ODAĞI:\n"
        + focus_text
        + "\n\n"
        + f"{header}:\n"
        "- Temel Olaylar:\n"
        + "\n".join(event_lines)
        + "\n- Sinyaller:\n"
        + "\n".join(signal_lines)
        + "\n- Ozet:\n"
        + (summary or "No intel summary.")
        + f"\n- Guven Skoru: {confidence:.2f}"
        + (f"\n- Guncellik: {recency_note}" if recency_note else "")
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


def is_intel_query(text: str) -> bool:
    low = _normalize_text(text)
    words = [w for w in re.findall(r"[a-z0-9]+", low) if w]
    smalltalk_terms = {
        "selam",
        "merhaba",
        "naber",
        "nasilsin",
        "iyiyim",
        "tesekkurler",
        "tesekkur",
        "saol",
        "gunaydin",
        "iyiaksamlar",
    }
    if len(words) <= 5 and any(w in smalltalk_terms for w in words):
        return False

    keyword_groups = (
        ("market", "crypto", "kripto", "btc", "eth", "altcoin", "finance", "finans", "fed", "faiz", "enflasyon"),
        ("security", "guvenlik", "breach", "hack", "sizinti", "ihlal", "exploit", "ransomware"),
        ("macro", "makro", "geopolit", "jeopolitik", "sinyal", "risk", "impact", "etki", "senaryo"),
    )
    if any(k in low for group in keyword_groups for k in group):
        return True
    analysis_patterns = (
        r"\bwhat is happening\b",
        r"\bwhat should i watch\b",
        r"\bneyi izlemeliyim\b",
        r"\bne oluyor\b",
        r"\banaliz\b",
        r"\bdegerlendir\b",
        r"\bimpact\b",
        r"\bhaber\b",
        r"\bguncel\b",
        r"\bson durum\b",
        r"\bneden dustu\b",
        r"\bneden yukseldi\b",
        r"\bris(k|k)\b",
    )
    return any(re.search(p, low) for p in analysis_patterns)


def _build_intel_context_from_events(events: list[Any]) -> dict[str, Any]:
    key_events: list[dict[str, Any]] = []
    signals: list[str] = []
    for ev in events[:10]:
        title = str(getattr(ev, "title", "") or "").strip()
        if not title:
            continue
        summary = str(getattr(ev, "summary", "") or "").strip()
        category = str(getattr(ev, "category", "other") or "other")
        source = str(getattr(ev, "source", "unknown") or "unknown")
        score = float(getattr(ev, "final_score", 0.0) or 0.0)
        importance = int(getattr(ev, "importance", 0) or 0)
        tags = list(getattr(ev, "tags", []) or [])[:4]
        timestamp = getattr(ev, "timestamp", None)
        key_events.append(
            {
                "title": title,
                "summary": summary[:220],
                "category": category,
                "source": source,
                "score": round(score, 4),
                "importance": importance,
                "tags": tags,
                "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else "",
            }
        )
        if any(k in _normalize_text(summary + " " + title) for k in ("risk", "breach", "outage", "volatility")):
            sig = f"risk:{title}"
            if sig not in signals:
                signals.append(sig)
        if len(key_events) >= 5:
            break
    summary_text = " | ".join([f"{e['title']} ({e['category']})" for e in key_events[:3]]) if key_events else ""
    confidence = 0.0
    if key_events:
        confidence = sum(float(e["score"]) for e in key_events) / float(len(key_events))
        confidence = max(0.0, min(1.0, confidence))
    return {
        "key_events": key_events,
        "summary": summary_text[:900],
        "signals": signals[:8],
        "confidence": round(confidence, 4),
        "recency_note": "latest_events",
        "query_focus": {},
    }


def _build_intel_injection_text(intel_context: dict[str, Any], compact_summary: str, max_chars: int = 2000) -> str:
    events = intel_context.get("key_events") or []
    event_lines: list[str] = []
    for item in events[:5]:
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()[:140]
        event_lines.append(f"- [{title}]: {summary}")
    if not event_lines:
        event_lines = ["- Yuksek oncelikli olay bulunamadi."]
    block = (
        "INTEL_CONTEXT:\n"
        "- Key Events:\n"
        + "\n".join(event_lines)
        + "\n\nINTEL_SUMMARY:\n"
        + (compact_summary or "Yeterli intel ozeti yok.")
    )
    return block[:max_chars]


def validate_response(text: str) -> bool:
    valid, _ = validate_response_detailed(text)
    return valid


def normalize_intel_response(text: str) -> str:
    out = str(text or "").strip()
    if not out:
        return out
    replacements = {
        r"(?im)^\s*(?:\d+[\).\s-]*)?\s*key\s*insight\s*:?\s*$": "1. Temel İçgörü",
        r"(?im)^\s*(?:\d+[\).\s-]*)?\s*temel\s*icgoru\s*:?\s*$": "1. Temel İçgörü",
        r"(?im)^\s*(?:\d+[\).\s-]*)?\s*why\s*it\s*matters\s*:?\s*$": "2. Neden Önemli",
        r"(?im)^\s*(?:\d+[\).\s-]*)?\s*neden\s*onemli\s*:?\s*$": "2. Neden Önemli",
        r"(?im)^\s*(?:\d+[\).\s-]*)?\s*risk\s*/\s*opportunity\s*:?\s*$": "3. Risk / Fırsat",
        r"(?im)^\s*(?:\d+[\).\s-]*)?\s*risk\s*/\s*firsat\s*:?\s*$": "3. Risk / Fırsat",
        r"(?im)^\s*(?:\d+[\).\s-]*)?\s*what\s*to\s*watch\s*:?\s*$": "4. Ne İzlenmeli",
        r"(?im)^\s*(?:\d+[\).\s-]*)?\s*ne\s*izlenmeli\s*:?\s*$": "4. Ne İzlenmeli",
    }
    for pattern, repl in replacements.items():
        out = re.sub(pattern, repl, out)
    return out


def validate_response_detailed(text: str) -> tuple[bool, str]:
    normalized_text = normalize_intel_response(text)
    low = _normalize_text(str(normalized_text or ""))
    if not low.strip():
        return False, "empty"
    words = [w for w in re.findall(r"[a-z0-9_]+", low) if w]
    if len(words) < 22:
        return False, "too_short"
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
    if len(words) < 120 and any(p in low for p in banned_generic):
        return False, "generic_phrase"

    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    list_like = 0
    for line in lines:
        if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+[\).\s-]+", line):
            list_like += 1
    if lines and (list_like / max(1, len(lines))) > 0.92 and len(words) < 45:
        return False, "list_style_weak"

    if not _looks_turkish(low):
        if len(words) < 50:
            return False, "non_turkish_content"

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
    analytic_markers = (
        "bu nedenle",
        "sonucunda",
        "tetikler",
        "baski",
        "etki",
        "risk",
        "firsat",
        "izlenmeli",
        "kisa vade",
    )
    if len(words) < 45 and not any(m in low for m in (*causal_markers, *analytic_markers)):
        return False, "low_information"

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
    if summary_overlap >= 2 and concept_overlap >= 3:
        return True, "summary_overlap"
    if category_hit >= 1 and concept_overlap >= 2:
        return True, "category_overlap"
    if concept_overlap >= 4 and (summary_overlap >= 1 or title_hit >= 1):
        return True, "concept_overlap"
    if category_hit >= 1 and summary_overlap >= 1 and concept_overlap >= 3:
        return True, "category_summary_overlap"
    return False, "insufficient_intel_reference"


def score_response(response: str) -> dict[str, float]:
    low = str(response or "").lower()
    words = [w for w in re.findall(r"[a-zA-Z0-9_]+", low) if w]
    length_score = min(1.0, len(words) / 220.0)
    causal_score = 1.0 if any(x in low for x in ("because", "leads to", "implies", "therefore", "bu nedenle")) else 0.35
    intel_score = 1.0 if any(x in low for x in ("temel icgoru", "ne izlenmeli", "sinyal", "guven", "key insight", "what to watch")) else 0.4
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
            "1. Temel İçgörü\n"
            "Elde güçlü bir olay kümesi yok; mevcut sinyal yoğunluğu düşük olduğu için yüksek güvenli bir yön çıkarımı yapmak doğru değil.\n\n"
            "2. Neden Önemli\n"
            "Sinyal zayıfken agresif yorum yapmak hatalı karar riskini artırır; bu nedenle kısa vadede doğrulama sinyali beklemek daha rasyoneldir.\n\n"
            "3. Risk / Fırsat\n"
            "Risk: zayıf veriden kesin hüküm üretmek. Fırsat: yeni olaylar geldikçe daha temiz bir trend yakalama imkanı.\n\n"
            "4. Ne İzlenmeli\n"
            "Önümüzdeki 24-48 saatte yüksek skorlu yeni olay sayısı, tekrar eden anomali sinyalleri ve güven skorunun 0.60 üstüne çıkışı izlenmeli."
        )

    top = events[0]
    title = str(top.get("title") or "Oncelikli olay")
    category = str(top.get("category") or "other")
    score = float(top.get("effective_score") or top.get("score") or 0.0)
    signal = str(signals[0] if signals else f"risk:{title}")
    user_focus_tokens = _extract_tokens(user_text)
    focus_text = " / ".join(sorted(list(user_focus_tokens))[:3]) if user_focus_tokens else "kullanici odagi"

    return (
        "1. Temel İçgörü\n"
        f"En güçlü sinyal '{title}' ({category}) olayıdır; etkin skoru {score:.2f} ile şu an tabloyu belirleyen ana başlık budur.\n\n"
        "2. Neden Önemli\n"
        f"Bu olay '{signal}' sinyaliyle aynı yönde ilerlediği için kısa vadede {focus_text} tarafına baskı aktarımı üretebilir; "
        f"güven skoru {confidence:.2f} olduğu için sinyal kullanılabilir ama teyit gerektirir.\n\n"
        "3. Risk / Fırsat\n"
        "Risk: takip verisi zayıflarsa sinyal hızla bozulabilir. Fırsat: ilişkili yüksek skorlu olaylar kümelenirse daha net yön oluşur.\n\n"
        "4. Ne İzlenmeli\n"
        "Önümüzdeki 24-48 saatte benzer sinyallerin artıp artmadığı, risk etiketli olay hızındaki değişim ve güven skorunun yönü takip edilmeli."
    )


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request, services: BackendServices = Depends(get_services)) -> ChatResponse:
    user_id = str(getattr(request.state, "user_id", "default"))
    ai_source = "openclaw" if services.settings.openclaw_enabled else "openai_direct"
    text = (payload.text or "").strip()
    if not text:
        return ChatResponse(
            reply="Bos mesaj gonderilemez.",
            session_id=payload.session_id or "",
            metrics={"ok": False, "intel_used": False, "intel_event_count": 0},
        )
    logger.info(
        "CHAT_INCOMING user_id=%s session_id_hint=%s text_chars=%s",
        user_id,
        str(payload.session_id or ""),
        len(text),
    )

    guard = services.cost_guard.check_and_track(text)
    if not guard.ok:
        return ChatResponse(
            reply=guard.reason,
            session_id=payload.session_id or "",
            metrics={"source": "guard", "ok": False, "usage": guard.usage or {}, "intel_used": False, "intel_event_count": 0},
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
                "intel_used": bool(prev_metrics.get("intel_used", False)),
                "intel_event_count": int(prev_metrics.get("intel_event_count", 0) or 0),
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
    latest_events = services.intel.get_latest_events(limit=10)
    logger.info("CHAT_LATEST_EVENTS count=%s", len(latest_events))
    intel_query = is_intel_query(text)
    relevant_intel_context: dict[str, Any] = {}
    if intel_query:
        try:
            relevant_intel_context = select_relevant_intel_context(
                services.intel,
                query=text,
                user_id=user_id,
                max_events=5,
            )
        except Exception as exc:
            logger.info("CHAT_INTEL_SELECT_ERROR error=%s", exc)
            relevant_intel_context = {}
    relevant_events = relevant_intel_context.get("key_events") or []
    intel_mode = bool(intel_query and relevant_events)
    if not intel_query:
        mode_reason = "query_not_intel"
    elif not relevant_events:
        mode_reason = "no_relevant_events"
        logger.info("CHAT_INTEL_SELECTED count=0 titles=none")
    else:
        mode_reason = "relevant_events"
    logger.info("CHAT_INTEL_MODE enabled=%s reason=%s", intel_mode, mode_reason)
    logger.info("INTEL_MODE=%s reason=%s", "on" if intel_mode else "off", mode_reason)
    intel_context: dict[str, Any] = {}
    intel_data = ""
    user_focus = "general"
    injected_event_count = 0
    if intel_mode:
        intel_context = relevant_intel_context
        compact_intel = summarize_intel_context(intel_context, max_chars=1000)
        selected_events = intel_context.get("key_events") or []
        injected_event_count = len(selected_events)
        selected_titles = [str(item.get("title") or "").strip() for item in selected_events if str(item.get("title") or "").strip()]
        logger.info(
            "CHAT_INTEL_SELECTED count=%s titles=%s",
            injected_event_count,
            " | ".join(selected_titles[:5]) if selected_titles else "none",
        )
        logger.info("INTEL_FETCH_SUCCESS count=%s", injected_event_count)
        intel_data = _build_intel_injection_text(intel_context, compact_intel, max_chars=2000)
        logger.info("INTEL_INJECTED count=%s chars=%s", injected_event_count, len(intel_data))
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
    if intel_mode:
        intel_block = intel_data if intel_data else "INTEL_CONTEXT:\n- Key Events:\n- Yuksek oncelikli olay yok.\n\nINTEL_SUMMARY:\nYeterli intel yok."
        intel_system_prompt = (
            "AYEX-IA olarak yalnizca Turkce yanit ver.\n"
            "Ingilizce kelime, baslik veya cumle kullanma.\n\n"
            "Rol:\n"
            "- Sen bir istihbarat analiz sistemisin.\n"
            "- Ham veriyi listeleme; anlam ve neden-sonuc uret.\n"
            "- Secilen olay/sinyalleri dogrudan kullan; baglamsiz genel bilgiye kayma.\n\n"
            "Aşağıdaki secilmis istihbarat verisine dayan:\n\n"
            f"{intel_block}\n\n"
            f"Kullanici odagi: {user_focus}\n\n"
            "Zorunlu kurallar:\n"
            "- Yanit Turkce olacak, dogal ve net olacak.\n"
            "- Secilen olay/sinyalleri ad veya kavram seviyesinde acikca referansla.\n"
            "- En az bir olay basligini aynen yazarak referans ver.\n"
            "- Neden-sonuc zinciri kur: 'bu nedenle', 'sonucunda', 'tetikler' gibi acik baglantilar kullan.\n"
            "- Kisa vadeli etkileri belirt (onumuzdeki 24-48 saat / kisa vade).\n"
            "- Bos, genel, ezber cümle kullanma.\n"
            "- Teknik ama anlasilir ol; dolgu metin yazma.\n\n"
            "Yanit yapisi (basliklar opsiyonel, ancak bu 4 boyutu kapsa):\n"
            "- Temel İçgörü\n"
            "- Neden Önemli\n"
            "- Risk / Fırsat\n"
            "- Ne İzlenmeli\n"
        )
        profile_context_for_model = f"{services.profile.prompt_context()}\n\n{intel_system_prompt}"
    else:
        profile_context_for_model = services.profile.prompt_context()

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
    final_response_mode = "llm"
    model_used_intel = False
    fallback_used_intel = False
    used_intel = False
    if intel_mode:
        hard_fail_reasons = {"empty", "too_short", "generic_phrase", "low_information"}
        reply = normalize_intel_response(reply)
        model_used_intel, intel_reason = did_use_intel_detailed(reply, intel_context)
        if model_used_intel and injected_event_count > 0:
            logger.info("INTEL_USED_TRUE reason=model")
        else:
            logger.info("INTEL_USED_FALSE reason=%s", intel_reason)
        is_valid, validation_reason = validate_response_detailed(reply)
        hard_validation_fail = (not is_valid) and (validation_reason in hard_fail_reasons)
        needs_retry = (not model_used_intel and injected_event_count > 0) or hard_validation_fail
        logger.info(
            "CHAT_VALIDATION stage=initial passed=%s intel_used=%s reason=%s hard_fail=%s retry=%s",
            is_valid,
            model_used_intel,
            "ok" if is_valid else validation_reason,
            hard_validation_fail,
            needs_retry,
        )
        if needs_retry:
            reason_type = "intel_missing" if not model_used_intel and injected_event_count > 0 else validation_reason
            logger.info("CHAT_REJECT stage=initial reason=%s", reason_type)
            logger.info("RESPONSE_REJECTED_GENERIC reason=%s", reason_type)
            retry_profile_context = (
                f"{profile_context_for_model}\n\n"
                "Onceki yanit yeterli netlikte degil veya secili intel ile yeterince baglantili degil.\n"
                "Yanitini TEKRAR URET ve su kosullari karsila:\n"
                "- Sadece Turkce yaz.\n"
                "- Secilen istihbarat olay ve sinyallerini dogrudan kullan.\n"
                "- En az bir olay basligini acikca referansla.\n"
                "- Neden-sonuc iliskisini ve kisa vade etkisini belirt.\n"
                "- Gereksiz dolgu kullanma, ama formati dogal tut."
            )
            logger.info("CHAT_REGEN triggered=true")
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
                reply = normalize_intel_response(retry_reply)
                result = retry_result
            model_used_intel, intel_reason = did_use_intel_detailed(reply, intel_context)
            is_valid, validation_reason = validate_response_detailed(reply)
            hard_validation_fail = (not is_valid) and (validation_reason in hard_fail_reasons)
            needs_fallback = (not model_used_intel and injected_event_count > 0) or hard_validation_fail
            if model_used_intel and injected_event_count > 0:
                logger.info("INTEL_USED_TRUE reason=model")
            else:
                logger.info("INTEL_USED_FALSE reason=%s", intel_reason)
            logger.info(
                "CHAT_VALIDATION stage=regen passed=%s intel_used=%s reason=%s hard_fail=%s fallback=%s",
                is_valid,
                model_used_intel,
                "ok" if is_valid else validation_reason,
                hard_validation_fail,
                needs_fallback,
            )
            if not needs_fallback:
                final_response_mode = "regen"
            if needs_fallback:
                logger.info("REGEN_VALIDATION_FAILED reason=%s", validation_reason if not is_valid else intel_reason)
                logger.info("RESPONSE_REJECTED_AFTER_REGEN reason=%s", validation_reason if not is_valid else intel_reason)
                reply = build_safe_fallback_response(intel_context, text)
                if injected_event_count > 0:
                    fallback_used_intel = True
                    logger.info("INTEL_USED_TRUE reason=fallback")
                logger.info("CHAT_FALLBACK used=true")
                logger.info("SAFE_FALLBACK_USED")
                final_response_mode = "fallback"
        used_intel = bool(injected_event_count > 0 and (model_used_intel or fallback_used_intel))
        if final_response_mode != "fallback":
            logger.info("CHAT_FALLBACK used=false")
    logger.info("FINAL_RESPONSE_MODE=%s", final_response_mode)
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
            "intel_event_count": injected_event_count,
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
            "intel_event_count": injected_event_count,
        },
    )
