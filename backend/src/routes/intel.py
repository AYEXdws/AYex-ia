from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from backend.src.intel.intel_service import select_relevant_intel_context
from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices
from backend.src.services.market_decision import build_market_decision
from backend.src.services.proactive_briefing import build_proactive_briefing

router = APIRouter()


@router.get("/intel")
def intel_brief(request: Request, services: BackendServices = Depends(get_services)) -> dict:
    user_id = str(getattr(request.state, "user_id", "default"))
    daily = services.intel.get_daily_brief(user_id=user_id)
    proactive = build_proactive_briefing(services.intel, user_id=user_id, limit=6)
    latest_events = list(services.intel.get_latest_events(limit=20) or [])
    return {
        **(daily or {}),
        "proactive": proactive,
        "market_focus": _build_market_focus(services=services, user_id=user_id, latest_events=latest_events),
        "domain_focus": _build_domain_focus(latest_events),
    }


def _build_market_focus(*, services: BackendServices, user_id: str, latest_events: list) -> dict:
    prompts = {
        "crypto": "1-2 ay icin hangi kripto daha mantikli?",
        "equities": "1-2 ay icin hangi hisse daha mantikli?",
    }
    decisions: dict[str, dict] = {}
    for key, query in prompts.items():
        intel_context = select_relevant_intel_context(
            services.intel,
            query,
            user_id=user_id,
            max_events=8,
        )
        decisions[key] = build_market_decision(
            text=query,
            intel_context=intel_context,
            latest_events=latest_events,
        ).as_dict()
    decisions["macro"] = _build_macro_focus(latest_events)
    return decisions


def _build_domain_focus(latest_events: list) -> dict:
    return {
        "world": _build_source_focus(
            latest_events,
            label="World",
            sources={"bbc_world", "reuters"},
            fallback="Dunya tarafinda taze bir event yok.",
        ),
        "cyber": _build_source_focus(
            latest_events,
            label="Cyber",
            sources={"the_hacker_news"},
            fallback="Siber tarafta taze bir event yok.",
        ),
    }


def _build_macro_focus(latest_events: list) -> dict:
    macro_event = next(
        (
            event
            for event in latest_events
            if str(getattr(event, "source", "") or "").strip().lower() == "er_api"
            or "makro" in [str(tag).strip().lower() for tag in (getattr(event, "tags", []) or [])]
        ),
        None,
    )
    if macro_event is None:
        return {
            "active": False,
            "summary": "Makro tarafi icin taze bir sinyal yok.",
            "signal": "unknown",
            "reasons": [],
        }

    importance = int(getattr(macro_event, "importance", 5) or 5)
    summary = str(getattr(macro_event, "summary", "") or "").strip()
    title = str(getattr(macro_event, "title", "") or "").strip()
    signal = "watch"
    if importance >= 8:
        signal = "stress"
    elif importance <= 5:
        signal = "calm"
    reasons = [title] if title else []
    if summary:
        reasons.append(summary[:220])
    return {
        "active": True,
        "summary": title or "Makro ozet guncellendi.",
        "signal": signal,
        "reasons": reasons[:2],
    }


def _build_source_focus(latest_events: list, *, label: str, sources: set[str], fallback: str) -> dict:
    event = next(
        (
            item
            for item in latest_events
            if str(getattr(item, "source", "") or "").strip().lower() in sources
        ),
        None,
    )
    if event is None:
        return {
            "active": False,
            "summary": fallback,
            "signal": "unknown",
            "reasons": [],
            "freshness": "unknown",
        }

    ts = getattr(event, "timestamp", None)
    freshness = _freshness_label(ts)
    summary = str(getattr(event, "title", "") or "").strip() or fallback
    detail = str(getattr(event, "summary", "") or "").strip()
    signal = "stale" if freshness in {"12h+", "24h+", "72h+"} else "fresh"
    reasons = [f"Tazelik: {freshness}"]
    if detail:
        reasons.append(detail[:220])
    return {
        "active": True,
        "summary": summary,
        "signal": signal,
        "reasons": reasons[:2],
        "freshness": freshness,
        "source": str(getattr(event, "source", "") or "").strip(),
    }


def _freshness_label(ts) -> str:
    if not isinstance(ts, datetime):
        return "unknown"
    event_utc = ts.astimezone(timezone.utc) if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (datetime.now(timezone.utc) - event_utc).total_seconds() / 3600.0)
    if age_hours < 2:
        return "<2h"
    if age_hours < 6:
        return "<6h"
    if age_hours < 12:
        return "<12h"
    if age_hours < 24:
        return "12h+"
    if age_hours < 72:
        return "24h+"
    return "72h+"
