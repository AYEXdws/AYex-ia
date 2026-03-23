from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from backend.src.intel.intel_service import get_intel_summary, select_relevant_intel_context
from backend.src.services.market_decision import is_market_decision_query


@dataclass(frozen=True)
class QueryContextBundle:
    intent_category: str
    response_style: str
    response_mode: str
    profile_data: dict[str, Any]
    profile_context: str
    memory_context: str
    long_memory_text: str
    merged_memory: str
    memory_hits: int
    intel_context: dict[str, Any]
    intel_context_text: str
    response_policy: str
    memory_preview: tuple[str, ...]
    intel_preview: tuple[str, ...]


@dataclass(frozen=True)
class ToolEvidence:
    selected_tool: str = ""
    text: str = ""
    has_data: bool = False


def build_query_context(
    services: Any,
    *,
    text: str,
    session_id: str,
    user_id: str,
    use_profile: bool = True,
    max_intel_events: int = 6,
) -> QueryContextBundle:
    profile_data = {}
    profile_context = ""
    if use_profile:
        try:
            profile_data = dict(getattr(services.profile, "load")() or {})
        except Exception:
            profile_data = {}
        try:
            profile_context = str(getattr(services.profile, "prompt_context")() or "").strip()
        except Exception:
            profile_context = ""

    profile_style = str(profile_data.get("response_style") or "")
    style_service = getattr(services, "style", None)
    if style_service and hasattr(style_service, "detect"):
        style_decision = getattr(style_service, "detect")(text, profile_style=profile_style)
    else:
        style_decision = SimpleNamespace(style="normal", reason="fallback")
    response_style = str(getattr(style_decision, "style", "normal") or "normal")

    intent_service = getattr(services, "intents", None)
    if intent_service and hasattr(intent_service, "route"):
        intent_result = getattr(intent_service, "route")(text)
    else:
        intent_result = SimpleNamespace(category="chat")
    intent_category = str(getattr(intent_result, "category", "chat") or "chat")
    response_mode = detect_response_mode(
        text,
        intent_category=intent_category,
        response_style=response_style,
    )

    memory_context = ""
    try:
        memory_context = str(
            getattr(services.chat_store, "recall_context_text")(
                query=text,
                exclude_session_id=session_id,
                limit=4,
            )
            or ""
        ).strip()
    except Exception:
        memory_context = ""

    long_memory_text = ""
    long_memory_hits = 0
    try:
        long_memory_ctx = getattr(services.long_memory, "build_context")(query=text, limit=4, user_id=user_id)
        long_memory_text = str(getattr(long_memory_ctx, "as_text")() or "").strip()
        long_memory_hits = len(getattr(long_memory_ctx, "conversation_hits", []) or []) + len(
            getattr(long_memory_ctx, "event_hits", []) or []
        )
    except Exception:
        long_memory_text = ""
        long_memory_hits = 0

    memory_hits = 0 if not memory_context else max(1, memory_context.count("\n"))
    if long_memory_text:
        memory_hits += long_memory_hits

    intel_context: dict[str, Any] = {}
    intel_context_text = ""
    try:
        intel_context = (
            select_relevant_intel_context(
                getattr(services, "intel"),
                text,
                user_id=user_id,
                max_events=max(3, min(10, int(max_intel_events or 6))),
            )
            or {}
        )
    except Exception:
        intel_context = {}

    try:
        daily_intel = str(get_intel_summary(getattr(services, "intel"), user_id=user_id, max_chars=1000) or "").strip()
    except Exception:
        daily_intel = ""

    intel_parts: list[str] = []
    if intel_context:
        summary = str(intel_context.get("summary") or "").strip()
        signals = ", ".join([str(x).strip() for x in (intel_context.get("signals") or []) if str(x).strip()][:6])
        events = list(intel_context.get("key_events") or [])[:6]
        rows: list[str] = []
        for item in events:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            row = f"- {title}"
            item_summary = str(item.get("summary") or "").strip()
            if item_summary:
                row += f": {item_summary[:180]}"
            rows.append(row)
        if summary:
            intel_parts.append(f"Intel ozeti:\n{summary[:900]}")
        if rows:
            intel_parts.append("Sorguya en ilgili eventler:\n" + "\n".join(rows))
        if signals:
            intel_parts.append(f"Intel sinyalleri: {signals}")
    if daily_intel:
        intel_parts.append(f"Guncel brief:\n{daily_intel[:1000]}")
    intel_context_text = "\n\n".join([part for part in intel_parts if part.strip()])

    merged_memory = "\n\n".join([x for x in [memory_context, long_memory_text] if x.strip()])
    memory_preview = _memory_preview(memory_context, long_memory_text)
    intel_preview = _intel_preview(intel_context)
    response_policy = build_response_policy(
        text,
        intent_category=intent_category,
        response_style=response_style,
        response_mode=response_mode,
        profile_data=profile_data,
        intel_context=intel_context,
    )

    return QueryContextBundle(
        intent_category=intent_category,
        response_style=response_style,
        response_mode=response_mode,
        profile_data=profile_data,
        profile_context=profile_context,
        memory_context=memory_context,
        long_memory_text=long_memory_text,
        merged_memory=merged_memory,
        memory_hits=memory_hits,
        intel_context=intel_context,
        intel_context_text=intel_context_text,
        response_policy=response_policy,
        memory_preview=memory_preview,
        intel_preview=intel_preview,
    )


def collect_tool_evidence(services: Any, *, intent_category: str, text: str) -> ToolEvidence:
    try:
        tool_result = getattr(services.tools, "route_and_run")(intent=intent_category, text=text)
    except Exception:
        return ToolEvidence()

    try:
        evidence_text = str(getattr(tool_result, "evidence_text")() or "").strip()
    except Exception:
        evidence_text = ""
    has_data = bool(getattr(tool_result, "has_data", False))
    selected_tool = str(getattr(tool_result, "selected_tool", "") or "")
    return ToolEvidence(selected_tool=selected_tool, text=evidence_text, has_data=has_data)


def build_explainability_trace(
    *,
    query_ctx: QueryContextBundle,
    proactive_brief: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    route: str = "",
    model: str = "",
    tool: str = "",
) -> dict[str, Any]:
    proactive_brief = dict(proactive_brief or {})
    decision = dict(decision or {})
    return {
        "route": route,
        "model": model,
        "intent": query_ctx.intent_category,
        "response_mode": query_ctx.response_mode,
        "tool": tool,
        "memory": list(query_ctx.memory_preview),
        "intel": list(query_ctx.intel_preview),
        "briefing": str(proactive_brief.get("summary") or "").strip()[:320],
        "decision": str(decision.get("summary") or "").strip()[:260],
        "decision_asset": str(decision.get("asset") or "").strip(),
        "decision_stance": str(decision.get("stance") or "").strip(),
        "reasons": list(decision.get("reasons") or [])[:3],
        "risks": list(decision.get("risks") or [])[:2],
    }


def build_response_policy(
    text: str,
    *,
    intent_category: str,
    response_style: str,
    response_mode: str,
    profile_data: dict[str, Any] | None = None,
    intel_context: dict[str, Any] | None = None,
) -> str:
    profile_data = dict(profile_data or {})
    intel_context = dict(intel_context or {})
    low = _normalize(text)
    parts = [
        "Yanit kurali: once sonucu soyle, sonra kisa gerekce ver.",
        "Gereksiz gevezelik yapma. Bos dengecilik kurma. Ahmet'in anlayacagi net Turkce kullan.",
        "Teknik jargon varsa sadeleştir; 'ne oldu, neden onemli, Ahmet icin sonucu ne' mantigi ile acikla.",
        "Yanitin omurgasi kararli olsun. Ozellikle analiz ve secim sorularinda belirsiz gevezelik yapma.",
    ]

    if response_mode == "inventory":
        parts.append(
            "Bu bir canli durum envanteri sorusu. Feed bazli cevap ver: Kripto, Hisse, Makro, World, Cyber. "
            "Her satirda aktif/pasif durumu, freshness ve son eventi belirt."
        )
    elif response_mode == "decision":
        parts.append(
            "Bu bir karar modu cevabi. Ilk satirda tek hukum ver. Sonra en fazla 2 neden ve 1 risk yaz. "
            "Eski sohbeti gereksiz yere tasima; canli sinyali oncele."
        )
    elif response_mode == "analysis":
        parts.append(
            "Bu bir analiz modu cevabi. Gerekirse hedef, varsayim, plan, risk ve alternatif sirasi ile ilerle."
        )

    if response_style == "brief":
        parts.append("Cevap boyu: kisa. Gerekirse 2-4 cumle.")
    elif response_style == "deep":
        parts.append("Cevap boyu: detayli ama hala sonucu ilk kisimda ver.")

    market_decision = any(
        token in low
        for token in (
            "hangi coin",
            "hangi kripto",
            "hangi token",
            "hangi hisse",
            "almaliyim",
            "alayim",
            "almam lazim",
            "satmaliyim",
            "kisa vade",
            "kisa vadede",
            "1 ay",
            "2 ay",
            "bir ay",
            "iki ay",
            "en mantikli",
            "en guclu secenek",
            "ne alinur",
            "ne alinmali",
        )
    )
    if market_decision or intent_category == "market":
        parts.append(
            "Bu bir karar sorgusu. Ilk cumlede tek bir ana secenek ver. Ardindan en fazla 3 kisa gerekce ve 1 temel risk ver. "
            "Net edge yoksa bunu acikca soyle ve beklemeyi oner."
        )

    if any(token in low for token in ("neden", "acikla", "anlat", "yorumla", "analiz")):
        parts.append("Analiz yaparken karsilastirma ve neden-sonuc zinciri kur.")

    if intel_context:
        parts.append("Elindeki intel verisini once kendi icinde karsilastir, sonra cevapla.")
        if intel_context.get("timeframe_mode") == "compare":
            parts.append("Eski ve yeni veriyi ayir; degisimi tek cizgide ozetle.")

    feedback_style = str(profile_data.get("feedback_style") or "").strip().lower()
    if feedback_style in {"sert", "sert ve net", "net"}:
        parts.append("Ton: net, direkt, yumusatma yok; ama bos sertlik de yok.")

    work_framework = [str(item).strip() for item in (profile_data.get("work_framework") or []) if str(item).strip()]
    if response_mode == "analysis" and work_framework:
        parts.append("Ahmet'in tercih ettigi analiz sirasi: " + " > ".join(work_framework[:6]) + ".")

    return "\n".join(parts).strip()


def detect_response_mode(text: str, *, intent_category: str, response_style: str) -> str:
    low = _normalize(text)
    if _is_live_inventory_query(low):
        return "inventory"
    if is_market_decision_query(low):
        return "decision"
    if intent_category in {"search", "url_read", "agent_task"}:
        return "analysis"
    if any(token in low for token in ("analiz", "strateji", "plan", "karsilastir", "karşılaştır", "neden", "niye", "risk", "varsayim", "varsayım")):
        return "analysis"
    if response_style == "brief":
        return "brief"
    return "normal"


def _normalize(text: str) -> str:
    out = (text or "").strip().lower()
    repl = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
    }
    for src, dst in repl.items():
        out = out.replace(src, dst)
    return " ".join(out.split())


def _is_live_inventory_query(text: str) -> bool:
    markers = (
        "su an elinde",
        "şu an elinde",
        "elindeki canli veriler",
        "elindeki canlı veriler",
        "hangi canli veriler",
        "hangi canlı veriler",
        "guncel veriler neler",
        "güncel veriler neler",
        "canli veriler neler",
        "canlı veriler neler",
        "hangi feedler",
        "hangi feed'ler",
        "hangi veriler var",
        "neler goruyorsun",
        "neler görüyorsun",
    )
    return any(marker in text for marker in markers)


def _memory_preview(memory_context: str, long_memory_text: str) -> tuple[str, ...]:
    rows: list[str] = []
    for block in (memory_context, long_memory_text):
        for line in str(block or "").splitlines():
            clean = line.strip().lstrip("-").strip()
            if not clean:
                continue
            rows.append(clean[:140])
            if len(rows) >= 3:
                return tuple(rows)
    return tuple(rows)


def _intel_preview(intel_context: dict[str, Any]) -> tuple[str, ...]:
    rows: list[str] = []
    for item in list(intel_context.get("key_events") or [])[:3]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if title:
            rows.append(title[:140])
    return tuple(rows)
