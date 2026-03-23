from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from backend.src.routes.deps import get_services
from backend.src.schemas import ChatRequest, ChatResponse
from backend.src.services.container import BackendServices
from backend.src.services.model_router import ModelSelection
from backend.src.utils.logging import get_logger, log_event

router = APIRouter()
logger = get_logger(__name__)


def _format_all_events(
    events: list[Any],
    *,
    max_events: int = 20,
    max_chars: int = 4200,
    max_events_per_category: int = 8,
    max_summary_chars: int = 220,
) -> str:
    """Tum eventleri kategorize ederek metin haline getirir.

    Deterministic prompt butcesi:
    - once zaman sirasina gore sirala
    - kategori bazinda sinirla
    - toplam karakter butcesini gecme
    """
    if not events:
        return ""

    safe_max_events = max(1, min(60, int(max_events or 20)))
    safe_max_chars = max(800, min(20000, int(max_chars or 4200)))
    safe_per_category = max(1, min(20, int(max_events_per_category or 8)))
    safe_summary_chars = max(80, min(500, int(max_summary_chars or 220)))

    def _ts_key(event: Any) -> str:
        ts = getattr(event, "timestamp", None)
        return ts.isoformat() if hasattr(ts, "isoformat") else ""

    sorted_events = sorted(list(events or []), key=_ts_key, reverse=True)
    categories: dict[str, list[str]] = {}
    total_candidates = 0

    for ev in sorted_events:
        if total_candidates >= safe_max_events:
            break
        title = str(getattr(ev, "title", "") or "").strip()
        if not title:
            continue

        summary = str(getattr(ev, "summary", "") or "").strip()
        category = str(getattr(ev, "category", "diger") or "diger").strip().upper()
        source = str(getattr(ev, "source", "") or "").strip()
        timestamp = getattr(ev, "timestamp", None)
        ts_str = timestamp.isoformat() if hasattr(timestamp, "isoformat") else ""
        tags = list(getattr(ev, "tags", []) or [])[:4]

        entries = categories.setdefault(category, [])
        if len(entries) >= safe_per_category:
            continue

        entry = f"- {title}"
        if summary:
            entry += f"\n  {summary[:safe_summary_chars]}"

        meta_parts: list[str] = []
        if source:
            meta_parts.append(source)
        if ts_str:
            meta_parts.append(ts_str)
        if tags:
            meta_parts.append(", ".join([str(t) for t in tags if str(t).strip()]))
        if meta_parts:
            entry += f"\n  [{' | '.join(meta_parts)}]"

        entries.append(entry)
        total_candidates += 1

    if not categories:
        return ""

    segments: list[tuple[str, str]] = []
    for cat, entries in categories.items():
        segments.append(("header", f"\n{cat}:\n"))
        for entry in entries:
            segments.append(("event", f"{entry}\n"))

    used_chars = 0
    used_events = 0
    out_parts: list[str] = []
    for kind, chunk in segments:
        chunk_len = len(chunk)
        if used_chars + chunk_len > safe_max_chars:
            break
        out_parts.append(chunk)
        used_chars += chunk_len
        if kind == "event":
            used_events += 1

    hidden_events = max(0, total_candidates - used_events)
    if hidden_events > 0:
        suffix = f"\n... +{hidden_events} event daha var (prompt butcesi nedeniyle kisaltildi)\n"
        if used_chars + len(suffix) <= safe_max_chars:
            out_parts.append(suffix)

    return "".join(out_parts).strip()


def _build_system_prompt(
    intel_text: str,
    event_count: int,
    memory_context: str,
    profile_context: str,
) -> str:
    """System prompt olusturur. Veri bloklari once gelir."""
    parts: list[str] = []

    if intel_text:
        parts.append(
            "===== GUNCEL ISTIHBARAT "
            f"({event_count} kayit) =====\n"
            "Asagidaki veriler n8n otomasyon sisteminden her 15-30 dakikada guncellenir.\n"
            "GERCEK ve GUNCEL verilerdir. Bu verileri HER ZAMAN kullan.\n"
            "\"Elimde veri yok\" ASLA deme. Fiyat sorulursa bu rakamlari ver.\n"
            "Analiz istenirse bu verileri yorumla. Sorulmasa bile ilgili ise bahset.\n"
            f"{intel_text}\n"
            "===== VERI SONU ====="
        )

    parts.append(
        "Sen AYEX'sin. Ahmet'in kisisel dijital bilinci.\n\n"
        "AHMET'I TANIYORSUN:\n"
        "- 17 yasinda, Amasya, YKS sureci var ama asil kafasi projelerde\n"
        "- Kripto, siber guvenlik, yapay zeka, geopolitik hepsine merakli\n"
        "- AYEX-IA, HAL, MindBloom projelerini gelistiriyor\n"
        "- Katmanli dusunur, analitik zeka, anlam bagimlisi\n"
        "- Sert geri bildirim ister, yalakalik istemez\n\n"
        "NASIL KONUSURSUN:\n"
        "- Ahmet'le arkadasin gibi konus. Resmi ifade yasak.\n"
        "- Kisa sorulara kisa cevap.\n"
        "- Analiz gereken yerde derinles ama sade tut.\n"
        "- Bilmiyorsan 'bilmiyorum' de, uydurma.\n"
        "- Turkce yaz, teknik terimler English kalabilir.\n"
        "- Baslik, numara, madde isareti, bold kullanma. Duz yaz.\n"
        "- Yerlestirilmis event verisini kullan, harici kaynaga yonlendirme yapma.\n"
        "- Eventlerde olmayan bilgi icin 'o veri bende yok' de.\n\n"
        "DUSUNME BICIMIN:\n"
        "- Her mesajda once verilere bak, sonra istegi anla, sonra cevap ver.\n"
        "- Sorulmasa bile onemli bir gelisme varsa bahset.\n"
        "- Kategoriler arasi iliski kurup cikarim yap.\n"
        "- Ahmet'in gecmis konusmalarini ve tercihlerini hatirla."
    )

    if memory_context:
        parts.append(f"GECMIS KONUSMALARDAN HATIRLANAN:\n{memory_context}")
    if profile_context:
        parts.append(profile_context)

    parts.append(f"Su anki zaman: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC (Turkiye: UTC+3)")
    return "\n\n".join([p for p in parts if p.strip()])


def _select_model_simple(
    text: str,
    event_count: int,
    settings: Any,
) -> ModelSelection:
    """Basit model secimi."""
    chat_model = getattr(settings, "ayex_chat_model", "claude-haiku-4.5")
    reasoning_model = getattr(settings, "ayex_reasoning_model", "claude-sonnet-4.6")
    power_model = getattr(settings, "ayex_power_model", "gpt-5")

    low = (text or "").lower().strip()
    text_len = len(text or "")

    def _provider(model: str) -> str:
        model_low = str(model or "").lower()
        if any(x in model_low for x in ("claude", "haiku", "sonnet", "opus")):
            return "anthropic"
        return "openai"

    power_signals = (
        "almalıyım",
        "almaliyim",
        "almali",
        "satmalıyım",
        "satmaliyim",
        "satmali",
        "strateji",
        "yatırım",
        "yatirim",
        "portföy",
        "portfolio",
        "en karlı",
        "en karli",
        "risk analizi",
        "uzun vadede",
        "kısa vadede",
        "kisa vadede",
    )
    if any(s in low for s in power_signals):
        return ModelSelection(model=power_model, provider=_provider(power_model), reason="strategy_query", route="power")

    if text_len > 80 or event_count > 5:
        return ModelSelection(model=reasoning_model, provider=_provider(reasoning_model), reason="complex_query", route="reasoning")

    return ModelSelection(model=chat_model, provider=_provider(chat_model), reason="default", route="chat")


def _maybe_trigger_memory_summary(services: BackendServices, session_id: str) -> None:
    """Arka planda memory summary tetikler."""
    try:
        recent_messages = services.chat_store.messages(session_id, limit=80)
        if recent_messages and len(recent_messages) % 6 == 0:
            loop = asyncio.get_running_loop()
            loop.create_task(_async_memory_summary(services, session_id))
    except RuntimeError:
        threading.Thread(
            target=lambda: asyncio.run(_async_memory_summary(services, session_id)),
            daemon=True,
        ).start()
    except Exception:
        pass


async def _async_memory_summary(services: BackendServices, session_id: str) -> None:
    """Async memory summary."""
    messages: list[dict[str, Any]] = []
    try:
        retried = services.memory.process_retry_queue(openai_client=services.model.openai, max_items=2)
        if retried:
            logger.info("MEMORY_SUMMARY_RETRY_PROCESSED count=%s", retried)

        messages = services.chat_store.messages(session_id, limit=80)
        if messages:
            services.memory.summarize_and_store(
                messages=messages,
                session_id=session_id,
                openai_client=services.model.openai,
            )
    except Exception as exc:
        try:
            services.memory.queue_retry(session_id=session_id, messages=messages, reason=str(exc))
        except Exception:
            pass
        logger.warning("MEMORY_SUMMARY_FAILED error=%s", str(exc))


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, services: BackendServices = Depends(get_services)) -> ChatResponse:
    """Ana chat endpoint. Basit akis: veri topla -> LLM'e gonder -> cevap don."""
    text = (payload.text or "").strip()
    if not text:
        return ChatResponse(reply="Bos mesaj gonderilemez.", session_id=payload.session_id or "", metrics={"ok": False})

    user_id = str(getattr(request.state, "user_id", "ayex"))
    request_id = str(getattr(request.state, "request_id", ""))
    ai_source = "model_direct"
    log_event(logger, "chat_start", request_id=request_id, user_id=user_id, text_len=len(text))

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
        return ChatResponse(
            reply=reply,
            session_id=session.id,
            metrics={
                "source": ai_source,
                "ok": prev_ok,
                "latency_ms": 0,
                "cache_hit": True,
                "event_count": int(prev_metrics.get("event_count", 0) or 0),
            },
        )

    services.chat_store.append_message(session.id, role="user", text=text, source="user")
    history = services.chat_store.model_context(session.id, turns=services.settings.model_context_turns)

    all_events: list[Any] = []
    try:
        all_events = list(services.intel.store.get_all_events() or [])
    except Exception as exc:
        logger.info("CHAT_ALL_EVENTS_FETCH_FAIL error=%s", exc)
    prompt_max_events = max(1, int(getattr(services.settings, "intel_prompt_max_events", 20) or 20))
    prompt_max_chars = max(800, int(getattr(services.settings, "intel_prompt_max_chars", 4200) or 4200))
    intel_text = _format_all_events(
        all_events,
        max_events=prompt_max_events,
        max_chars=prompt_max_chars,
    )
    event_count = len(all_events)
    logger.info(
        "CHAT_INTEL_PROMPT_BUDGET events_total=%s max_events=%s max_chars=%s rendered_chars=%s",
        event_count,
        prompt_max_events,
        prompt_max_chars,
        len(intel_text),
    )

    memory_context = ""
    try:
        memory_context = services.memory.get_memory_context(text)
    except Exception as exc:
        logger.info("CHAT_MEMORY_CONTEXT_FAIL error=%s", exc)

    profile_context = ""
    try:
        profile_context = services.profile.prompt_context()
    except Exception as exc:
        logger.info("CHAT_PROFILE_CONTEXT_FAIL error=%s", exc)

    system_prompt = _build_system_prompt(
        intel_text=intel_text,
        event_count=event_count,
        memory_context=memory_context,
        profile_context=profile_context,
    )

    model_selection = _select_model_simple(
        text=text,
        event_count=event_count,
        settings=services.settings,
    )
    logger.info(
        "CHAT_FLOW user=%s text_len=%d events=%d model=%s route=%s",
        user_id,
        len(text),
        event_count,
        model_selection.model,
        model_selection.route,
    )

    result = None
    reply = ""
    try:
        result = services.model.run_action(
            text,
            workspace=payload.workspace,
            model=model_selection.model,
            history=history,
            profile_context=system_prompt,
            memory_context=memory_context,
            response_style="normal",
            route_name=f"chat_{model_selection.route}",
        )
        reply = str(getattr(result, "text", "") or "").strip()
    except Exception as exc:
        logger.error("CHAT_LLM_ERROR error=%s", str(exc))
        reply = ""

    if not reply or len(reply) < 10:
        reply = "Bir sorun olustu, tekrar dene."

    latency_ms = int(getattr(result, "latency_ms", 0) or 0)
    source = str(getattr(result, "source", "") or "openai_direct")
    used_model = str(getattr(result, "used_model", "") or model_selection.model)
    response_style = str(getattr(result, "response_style", "") or "normal")

    services.chat_store.append_message(
        session.id,
        role="assistant",
        text=reply,
        source=source,
        latency_ms=latency_ms,
        metrics={
            "ok": bool(getattr(result, "ok", True)),
            "model": used_model,
            "used_model": used_model,
            "route": model_selection.route,
            "event_count": event_count,
            "source": source,
            "mode": response_style,
            "response_style": response_style,
        },
    )

    try:
        profile_data = services.profile.load()
        services.long_memory.sync_profile(profile_data, user_id=user_id)
        services.long_memory.append_conversation(
            session_id=session.id,
            user_text=text,
            assistant_text=reply,
            intent="chat",
            style="normal",
            user_id=user_id,
        )
    except Exception as exc:
        logger.info("CHAT_LONG_MEMORY_FAIL error=%s", exc)

    _maybe_trigger_memory_summary(services, session.id)
    log_event(
        logger,
        "chat_result",
        request_id=request_id,
        user_id=user_id,
        session_id=session.id,
        model=used_model,
        source=source,
        latency_ms=latency_ms,
        event_count=event_count,
    )

    return ChatResponse(
        reply=reply,
        session_id=session.id,
        metrics={
            "model": used_model,
            "used_model": used_model,
            "latency_ms": latency_ms,
            "source": source,
            "mode": response_style,
            "response_style": response_style,
            "event_count": event_count,
        },
    )
