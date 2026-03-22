from __future__ import annotations

import asyncio
import re
import threading
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.src.intel.intel_service import build_intel_context, select_relevant_intel_context
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


def _schedule_memory_summary(services: BackendServices, messages: list[dict[str, Any]], session_id: str) -> None:
    async def _runner() -> None:
        try:
            stored = services.memory.summarize_and_store(
                messages=messages,
                session_id=session_id,
                openai_client=services.openclaw.openai,
            )
            if stored:
                logger.info("MEMORY_SUMMARY_STORED session_id=%s memory_id=%s", session_id, str(stored.get("id") or ""))
        except Exception as exc:
            logger.info("MEMORY_SUMMARY_FAIL session_id=%s error=%s", session_id, exc)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_runner())
    except RuntimeError:
        threading.Thread(target=lambda: asyncio.run(_runner()), daemon=True).start()


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


def format_intel_for_prompt(intel_data: dict) -> str:
    """Intel event'lerini LLM'e sade liste olarak sunar. Skor/sinyal/jargon yok."""
    if not intel_data:
        return ""

    events = intel_data.get("key_events") or []
    if not events:
        return ""

    lines = []
    for ev in events:
        title = ev.get("title", "")
        summary = ev.get("summary", "")
        category = ev.get("category", "")
        source = ev.get("source", "")
        timestamp = ev.get("timestamp", "")
        time_context = ev.get("time_context", "")

        parts = [f"- {title}"]
        if summary:
            parts.append(f"  {summary}")
        meta = []
        if category:
            meta.append(category)
        if source:
            meta.append(source)
        if timestamp:
            meta.append(timestamp)
        if time_context:
            meta.append(time_context)
        if meta:
            parts.append(f"  [{', '.join(meta)}]")
        lines.append("\n".join(parts))

    return "\n\n".join(lines)


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
        (
            "dunyada",
            "dunya",
            "neler oldu",
            "haberler",
            "gundem",
            "bugun ne",
            "son dakika",
            "gelismeler",
            "piyasalar",
            "ekonomi",
            "kripto",
            "siber",
            "guvenlik",
            "saldiri",
        ),
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


def is_general_news_query(text: str) -> bool:
    low = _normalize_text(text)
    news_triggers = (
        "dunyada",
        "dunya",
        "neler oldu",
        "haberler",
        "gundem",
        "bugun ne",
        "son dakika",
        "gelismeler",
        "piyasalar",
    )
    return any(token in low for token in news_triggers)


def detect_tone(user_message: str) -> str:
    msg = _normalize_text(user_message)
    if any(w in msg for w in ("ne dusunursun", "sence", "bence", " ya ", " yani ", "haha", "neyse")):
        return "casual"
    if any(w in msg for w in ("acil", "dikkat", "kritik", "hemen", "simdi")):
        return "urgent"
    if any(w in msg for w in ("analiz", "karsilastir", "acikla", "neden", "nasil", "detay")):
        return "analytical"
    return "normal"


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


def _build_intel_injection_text(intel_data: dict) -> str:
    """Intel verisini prompt'a enjekte eder. Skor ve jargon içermez."""
    if not intel_data:
        return ""

    formatted = format_intel_for_prompt(intel_data)
    if not formatted:
        return ""

    timeframe_mode = intel_data.get("timeframe_mode", "none")
    recency_note = intel_data.get("recency_note", "")

    header = "GUNCEL VERILER:"
    if timeframe_mode == "compare" and recency_note:
        header = f"KARSILASTIRMA VERILERI ({recency_note}):"
    elif recency_note and recency_note != "latest_events":
        header = f"VERILER ({recency_note}):"

    return f"\n{header}\n{formatted}\n"


def validate_response(text: str, intel_data: dict[str, Any] | None = None) -> bool:
    valid, _ = validate_response_detailed(text, intel_data=intel_data)
    return valid


def normalize_intel_response(response: str) -> str:
    """Cevap boşsa veya çok kısaysa uyarı döner, format müdahalesi yapmaz."""
    if not response or not response.strip():
        return ""
    return response.strip()


def validate_response_detailed(text: str, intel_data: dict[str, Any] | None = None) -> tuple[bool, str]:
    normalized_text = normalize_intel_response(text)
    low = _normalize_text(str(normalized_text or ""))
    if not low.strip():
        return False, "empty"
    words = [w for w in re.findall(r"[a-z0-9_]+", low) if w]
    if len(words) < 12:
        return False, "too_short"

    if not _looks_turkish(low):
        if len(words) < 20:
            return False, "non_turkish_content"

    if (intel_data or {}).get("key_events"):
        used, reason = did_use_intel_detailed(normalized_text, intel_data or {})
        if not used:
            return False, f"missing_event_reference:{reason}"

    return True, "ok"


def did_use_intel(response: str, intel_context: dict[str, Any]) -> bool:
    used, _ = did_use_intel_detailed(response, intel_context)
    return used


def did_use_intel_detailed(response: str, intel_context: dict[str, Any]) -> tuple[bool, str]:
    low = _normalize_text(str(response or ""))
    if not low.strip():
        return False, "empty_response"

    events = (intel_context or {}).get("key_events") or []
    if not events:
        return False, "no_intel_events"

    for item in events[:5]:
        title = _normalize_text(str(item.get("title") or "").strip())
        if not title:
            continue
        words = [w for w in re.findall(r"[a-z0-9_]+", title) if len(w) > 3]
        unique_words = list(dict.fromkeys(words))

        if len(unique_words) >= 2:
            matches = sum(1 for w in unique_words if w in low)
            if matches >= 2:
                return True, "title_word_overlap"
        elif len(unique_words) == 1 and unique_words[0] in low:
            return True, "title_single_word_overlap"

        if title in low:
            return True, "title_exact_match"

    return False, "no_event_reference"


def score_response(response: str) -> dict[str, float]:
    low = str(response or "").lower()
    words = [w for w in re.findall(r"[a-zA-Z0-9_]+", low) if w]
    length_score = min(1.0, len(words) / 220.0)
    causal_score = 1.0 if any(x in low for x in ("because", "leads to", "implies", "therefore", "bu nedenle")) else 0.35
    intel_score = 0.6  # doğal cevap base skoru, jargon araması yok
    return {
        "depth_score": round((length_score * 0.55) + (causal_score * 0.45), 4),
        "relevance_score": round((causal_score * 0.6) + (intel_score * 0.4), 4),
        "intel_usage_score": round(intel_score, 4),
    }


def build_safe_fallback_response(intel_data: dict[str, Any], query: str = "") -> str:
    events = (intel_data or {}).get("key_events") or []
    if not events:
        return "Şu an güncel veri gelmiyor, biraz sonra tekrar dene."

    titles = [ev.get("title", "") for ev in events[:3] if ev.get("title")]
    if not titles:
        return "Veri var ama içerik okunamadı, tekrar dene."

    return f"Bakıyorum ama model şu an düzgün cevap üretemedi. Elimdeki başlıklar: {', '.join(titles)}. Soruyu biraz daha spesifik sorabilir misin?"


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

    services.chat_store.append_message(session.id, role="user", text=text, source="user")
    history = services.chat_store.model_context(session.id, turns=services.settings.openclaw_context_turns)
    profile_data = services.profile.load()
    summary_memory_context = ""
    try:
        summary_memory_context = services.memory.get_memory_context(text)
        if summary_memory_context:
            logger.info("MEMORY_SUMMARY_CONTEXT_USED chars=%s", len(summary_memory_context))
    except Exception as exc:
        logger.info("MEMORY_SUMMARY_CONTEXT_FAIL error=%s", exc)
    detected_tone = detect_tone(text)
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
    latest_event_count = len(latest_events)
    logger.info("CHAT_LATEST_EVENTS count=%s", latest_event_count)
    general_news_query = is_general_news_query(text)
    aggressive_news_mode = bool(general_news_query and latest_event_count > 0)
    intel_query = bool(is_intel_query(text) or aggressive_news_mode)
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
    if aggressive_news_mode and not (relevant_intel_context.get("key_events") or []) and latest_event_count > 0:
        relevant_intel_context = _build_intel_context_from_events(latest_events)
        logger.info("CHAT_INTEL_FALLBACK source=latest_events reason=general_news_query")
    relevant_events = relevant_intel_context.get("key_events") or []
    intel_mode = bool(intel_query and relevant_events)
    if not intel_query:
        mode_reason = "query_not_intel"
    elif aggressive_news_mode and relevant_events:
        mode_reason = "general_news_with_latest_events"
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
        selected_events = intel_context.get("key_events") or []
        injected_event_count = len(selected_events)
        selected_titles = [str(item.get("title") or "").strip() for item in selected_events if str(item.get("title") or "").strip()]
        logger.info(
            "CHAT_INTEL_SELECTED count=%s titles=%s",
            injected_event_count,
            " | ".join(selected_titles[:5]) if selected_titles else "none",
        )
        logger.info("INTEL_FETCH_SUCCESS count=%s", injected_event_count)
        intel_data = _build_intel_injection_text(intel_context)
        logger.info("INTEL_INJECTED count=%s chars=%s", injected_event_count, len(intel_data))
        user_focus = extract_user_focus(services, session.id, text)
    memory_hits = 0 if not memory_context else max(1, memory_context.count("\n"))
    if long_memory_text:
        memory_hits += len(long_memory_ctx.conversation_hits) + len(long_memory_ctx.event_hits)
    if summary_memory_context:
        memory_hits += max(1, summary_memory_context.count("\n"))
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
    profile_prompt_base = services.profile.prompt_context()
    if summary_memory_context:
        profile_prompt_base = f"{profile_prompt_base}\n\n{summary_memory_context}"
    if intel_mode:
        intel_system_prompt = f"""Sen AYEX'sin. Ahmet'in istihbarat sistemisin ama ondan önce dostsun.

AHMET'İ TANIYORSUN:
- 17 yaşında, Amasya, YKS süreci var ama asıl kafası projelerde
- Kripto, siber güvenlik, yapay zeka, geopolitik — hepsine meraklı
- Sert konuşmayı sever, yalakalık istemez, dolgu istemez

NASIL KONUŞURSUN:
- Ahmet'le arkadaşın gibi konuş. Resmi ve mesafeli kalıplar kullanma.
- Kısa sorulara kısa cevap. "nasılsın" derse 1-2 cümle, uzatma.
- Analiz gereken yerde derinleş ama sade tut. Başlık, numara, madde işareti kullanma.
- Bilmiyorsan "elimde o veri yok" de, uydurmak YASAK.
- Türkçe yaz, teknik terimler İngilizce kalabilir.

VERİ KULLANIMI:
Sana güncel veriler verilecek. Bu verilerle:
- Soruya doğrudan cevap ver. Veriyi olduğu gibi yapıştırma, kendi cümlenle yorumla.
- Sayıları kullan ama iç sistem terimleri kullanma.
- Karşılaştırma istenirse iki zaman dilimini yan yana koy, farkı açıkla.
- Genel soru gelirse (dünyada ne oldu) tüm kategorilerden özetle: kripto, haberler, siber güvenlik, ekonomi.
- Spesifik soru gelirse (BTC ne durumda) sadece o konuya odaklan, gereksiz bilgi ekleme.
- Eski ve yeni veri arasındaki değişimi fark et, trendi yorumla.
- "Elimde X var ama Y yok" diyebilirsin, bu dürüstlük.

{_build_intel_injection_text(intel_context) if intel_context else ""}

Şu anki zaman: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC
Türkiye saati: UTC+3
"""
        profile_context_for_model = (
            f"{profile_prompt_base}\n\n"
            f"Ahmet'in bu mesajdaki tonu: {detected_tone}. Buna göre cevapla.\n\n"
            f"{intel_system_prompt}"
        )
    else:
        profile_context_for_model = (
            f"{profile_prompt_base}\n\n"
            f"Ahmet'in bu mesajdaki tonu: {detected_tone}. Buna göre cevapla."
        )

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

    reply = normalize_intel_response(result.text or "")
    final_response_mode = "llm"
    used_intel = False
    if intel_mode:
        needs_retry = len(reply) < 15
        logger.info("CHAT_VALIDATION stage=initial short_or_empty=%s", needs_retry)
        if needs_retry:
            logger.info("CHAT_REGEN triggered=true reason=short_or_empty")
            retry_result = services.openclaw.run_action(
                model_input,
                workspace=payload.workspace,
                model=payload.model,
                history=history,
                profile_context=profile_context_for_model,
                memory_context=merged_memory,
                response_style=style_decision.style,
                route_name="chat_regen",
            )
            retry_reply = normalize_intel_response(retry_result.text or "")
            if retry_reply:
                reply = retry_reply
                result = retry_result
                final_response_mode = "regen"

            if len(reply) < 15:
                logger.info("CHAT_FALLBACK used=true reason=short_or_empty_after_regen")
                reply = build_safe_fallback_response(intel_context, text)
                final_response_mode = "fallback"
            else:
                logger.info("CHAT_FALLBACK used=false")
        else:
            logger.info("CHAT_FALLBACK used=false")
        used_intel = bool(injected_event_count > 0)
    elif not reply:
        reply = "Model yaniti alinamadi. Lutfen tekrar dene."
    logger.info("FINAL_RESPONSE_MODE=%s", final_response_mode)
    response_scores = score_response(reply)

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
    if result.ok:
        recent_messages = services.chat_store.messages(session.id, limit=80)
        if len(recent_messages) >= 6:
            logger.info("MEMORY_SUMMARY_TRIGGER session_id=%s message_count=%s", session.id, len(recent_messages))
            _schedule_memory_summary(services, recent_messages, session.id)

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
