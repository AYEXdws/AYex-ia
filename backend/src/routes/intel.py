from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.src.intel.intel_service import select_relevant_intel_context
from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices
from backend.src.services.live_feed_status import build_live_inventory, build_source_focus
from backend.src.services.market_decision import build_asset_signal_board, build_market_decision
from backend.src.services.proactive_briefing import build_proactive_briefing

router = APIRouter()


@router.get("/intel")
def intel_brief(request: Request, services: BackendServices = Depends(get_services)) -> dict:
    user_id = str(getattr(request.state, "user_id", "default"))
    profile_data = {}
    try:
        profile_data = dict(getattr(services.profile, "load")() or {})
    except Exception:
        profile_data = {}
    daily = services.intel.get_daily_brief(user_id=user_id)
    proactive = build_proactive_briefing(services.intel, user_id=user_id, limit=6)
    latest_events = list(services.intel.get_latest_events(limit=20) or [])
    inventory_events = _inventory_events(services)
    return {
        **(daily or {}),
        "proactive": proactive,
        "market_focus": _build_market_focus(
            services=services,
            user_id=user_id,
            latest_events=latest_events,
            profile_data=profile_data,
        ),
        "domain_focus": _build_domain_focus(inventory_events),
        "live_inventory": build_live_inventory(inventory_events),
        "persona_focus": _build_persona_focus(profile_data),
    }


def _inventory_events(services: BackendServices) -> list:
    store = getattr(getattr(services, "intel", None), "store", None)
    if store and hasattr(store, "get_all_events"):
        try:
            return list(getattr(store, "get_all_events")() or [])
        except Exception:
            pass
    return list(getattr(services.intel, "get_latest_events")(limit=80) or [])


def _build_market_focus(*, services: BackendServices, user_id: str, latest_events: list, profile_data: dict) -> dict:
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
            profile_data=profile_data,
        ).as_dict()
        decisions[f"{key}_signals"] = build_asset_signal_board(
            text=query,
            intel_context=intel_context,
            latest_events=latest_events,
            profile_data=profile_data,
            limit=4,
        )
    decisions["macro"] = _build_macro_focus(latest_events)
    return decisions


def _build_domain_focus(latest_events: list) -> dict:
    return {
        "world": build_source_focus(
            latest_events,
            label="World",
            sources={"bbc_world", "reuters"},
            fallback="Dunya tarafinda taze bir event yok.",
            fresh_hours=6.0,
            watch_hours=24.0,
            stale_hours=48.0,
        ),
        "cyber": build_source_focus(
            latest_events,
            label="Cyber",
            sources={"the_hacker_news"},
            fallback="Siber tarafta taze bir event yok.",
            fresh_hours=12.0,
            watch_hours=36.0,
            stale_hours=72.0,
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


def _build_persona_focus(profile_data: dict) -> dict:
    preferred_categories = [str(item).strip() for item in (profile_data.get("preferred_categories") or []) if str(item).strip()]
    focus_projects = [str(item).strip() for item in (profile_data.get("focus_projects") or []) if str(item).strip()]
    return {
        "assistant_name": str(profile_data.get("assistant_name") or "AYEX").strip(),
        "feedback_style": str(profile_data.get("feedback_style") or "").strip() or "net",
        "preferred_categories": preferred_categories[:3],
        "focus_projects": focus_projects[:3],
    }
