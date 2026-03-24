from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from backend.src.intel.intel_service import select_relevant_intel_context
from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices
from backend.src.services.decision_history import build_recent_decisions
from backend.src.services.live_feed_status import build_live_inventory, build_source_focus
from backend.src.services.market_decision import build_asset_signal_board, build_market_decision
from backend.src.services.proactive_briefing import build_proactive_briefing

router = APIRouter()

_PUBLIC_FEED_SPECS = (
    ("crypto", "Kripto", {"coingecko"}),
    ("equities", "Hisse", {"yahoo_finance"}),
    ("macro", "Makro", {"er_api"}),
    ("world", "World", {"bbc_world", "reuters"}),
    ("cyber", "Cyber", {"the_hacker_news", "bleeping_computer", "dark_reading"}),
)
_PUBLIC_SECTION_RULES = {
    "crypto": {"min_importance": 6, "min_score": 0.56, "max_age_hours": 72.0},
    "equities": {"min_importance": 6, "min_score": 0.56, "max_age_hours": 72.0},
    "macro": {"min_importance": 7, "min_score": 0.58, "max_age_hours": 96.0},
    "world": {"min_importance": 7, "min_score": 0.6, "max_age_hours": 36.0},
    "cyber": {"min_importance": 6, "min_score": 0.58, "max_age_hours": 72.0},
}


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
        "decision_history": build_recent_decisions(getattr(services, "chat_store", None), limit=6, sessions_window=18),
    }


@router.get("/public/intel")
def public_intel(services: BackendServices = Depends(get_services)) -> dict:
    inventory_events = _inventory_events(services)
    latest_events = list(services.intel.get_latest_events(limit=24) or [])
    market_focus = _build_market_focus(
        services=services,
        user_id="public",
        latest_events=latest_events,
        profile_data={},
    )
    domain_focus = _build_domain_focus(inventory_events)
    live_inventory = build_live_inventory(inventory_events)
    sections = _build_public_sections(
        inventory_events=inventory_events,
        market_focus=market_focus,
        domain_focus=domain_focus,
        live_inventory=live_inventory,
    )
    updated_at = _latest_timestamp_iso(inventory_events)
    return {
        "brand": "AYEXDWS",
        "updated_at": updated_at,
        "overview": _build_public_overview(sections=sections, updated_at=updated_at),
        "pulse": _build_public_pulse(market_focus=market_focus, domain_focus=domain_focus),
        "changed_today": _build_public_changed_today(sections),
        "sections": sections,
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
            sources={"the_hacker_news", "bleeping_computer", "dark_reading"},
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
    metrics = _extract_macro_metrics(summary)
    signal = "watch"
    if importance >= 8:
        signal = "stress"
    elif importance <= 5:
        signal = "calm"
    reasons = [title] if title else []
    for label in ("usdtry", "xauusd", "brent", "us10y", "risk_mode"):
        value = str(metrics.get(label) or "").strip()
        if not value:
            continue
        if label == "risk_mode":
            reasons.append(f"Risk modu: {value}")
        elif label == "us10y":
            reasons.append(f"US 10Y: {value}")
        elif label == "xauusd":
            reasons.append(f"XAU/USD: {value}")
        elif label == "brent":
            reasons.append(f"Brent: {value}")
        elif label == "usdtry":
            reasons.append(f"USD/TRY: {value}")
    if summary:
        reasons.append(summary[:220])
    return {
        "active": True,
        "summary": title or "Makro ozet guncellendi.",
        "signal": signal,
        "reasons": reasons[:4],
        "metrics": metrics,
    }


def _extract_macro_metrics(summary: str) -> dict[str, str]:
    text = str(summary or "").strip()
    patterns = {
        "usdtry": r"USD/TRY\s+([0-9]+(?:\.[0-9]+)?)",
        "xauusd": r"XAU/USD\s+([0-9]+(?:\.[0-9]+)?)",
        "brent": r"Brent\s+([0-9]+(?:\.[0-9]+)?)\s+USD",
        "us10y": r"US 10Y\s+([0-9]+(?:\.[0-9]+)?)%",
        "risk_mode": r"Risk modu su an\s+([a-zA-Z0-9\-]+)",
    }
    out: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip()
        if key == "us10y":
            value = f"{value}%"
        out[key] = value
    return out


def _build_persona_focus(profile_data: dict) -> dict:
    preferred_categories = [str(item).strip() for item in (profile_data.get("preferred_categories") or []) if str(item).strip()]
    focus_projects = [str(item).strip() for item in (profile_data.get("focus_projects") or []) if str(item).strip()]
    return {
        "assistant_name": str(profile_data.get("assistant_name") or "AYEX").strip(),
        "feedback_style": str(profile_data.get("feedback_style") or "").strip() or "net",
        "preferred_categories": preferred_categories[:3],
        "focus_projects": focus_projects[:3],
    }


def _build_public_sections(*, inventory_events: list, market_focus: dict, domain_focus: dict, live_inventory: dict) -> list[dict]:
    sections: list[dict] = []
    for key, label, sources in _PUBLIC_FEED_SPECS:
        matching = [
            event
            for event in list(inventory_events or [])
            if str(getattr(event, "source", "") or "").strip().lower() in sources
        ]
        matching.sort(key=_event_sort_key, reverse=True)
        curated = [event for event in matching if _is_publishable_public_event(event, key=key)]
        focus = _select_public_focus(key=key, market_focus=market_focus, domain_focus=domain_focus)
        feed_meta = dict((live_inventory.get("feeds") or {}).get(key) or {})
        lead_event = curated[0] if curated else (matching[0] if matching else None)
        sections.append(
            {
                "key": key,
                "label": label,
                "freshness": str(feed_meta.get("freshness") or "unknown"),
                "freshness_state": str(feed_meta.get("freshness_state") or "unknown"),
                "count_24h": int(feed_meta.get("count_24h") or 0),
                "published_count": len(curated),
                "summary": focus.get("summary") or feed_meta.get("summary") or f"{label} akisi icin sinyal yok.",
                "signal": focus.get("signal") or feed_meta.get("signal") or "unknown",
                "reasons": list(focus.get("reasons") or [])[:2],
                "headline": str(getattr(lead_event, "title", "") or "").strip() if lead_event else f"{label} akisi icin son event yok.",
                "items": [_event_to_public_item(event) for event in curated[:4]],
            }
        )
    return sections


def _select_public_focus(*, key: str, market_focus: dict, domain_focus: dict) -> dict:
    if key in {"crypto", "equities", "macro"}:
        return dict((market_focus or {}).get(key) or {})
    if key in {"world", "cyber"}:
        return dict((domain_focus or {}).get(key) or {})
    return {}


def _build_public_overview(*, sections: list[dict], updated_at: str) -> dict:
    active_count = sum(1 for section in sections if section.get("freshness_state") in {"fresh", "watch"})
    total_events = sum(int(section.get("published_count") or 0) for section in sections)
    strongest = next(
        (section for section in sections if section.get("signal") in {"conviction", "strong", "stress", "fresh"}),
        sections[0] if sections else {},
    )
    strongest_label = str((strongest or {}).get("label") or "Akis")
    strongest_summary = str((strongest or {}).get("summary") or "").strip()
    return {
        "headline": "Bes akistan gelen guncel sinyaller tek yuzeyde toplanir.",
        "summary": strongest_summary or "Canli akislardan gelen son sinyaller ayni omurgada okunur.",
        "updated_at": updated_at,
        "stats": {
            "active_feeds": active_count,
            "published_events": total_events,
            "lead_domain": strongest_label,
        },
    }


def _build_public_pulse(*, market_focus: dict, domain_focus: dict) -> list[dict]:
    pulse: list[dict] = []
    for key, label in (("crypto", "Kripto"), ("equities", "Hisse"), ("macro", "Makro")):
        row = dict((market_focus or {}).get(key) or {})
        if not row:
            continue
        pulse.append(
            {
                "label": label,
                "summary": str(row.get("summary") or "").strip() or f"{label} sinyali hazir.",
                "signal": str(row.get("signal") or "watch"),
            }
        )
    for key, label in (("world", "World"), ("cyber", "Cyber")):
        row = dict((domain_focus or {}).get(key) or {})
        pulse.append(
            {
                "label": label,
                "summary": str(row.get("summary") or "").strip() or f"{label} sinyali hazir.",
                "signal": str(row.get("signal") or "watch"),
            }
        )
    return pulse[:5]


def _event_to_public_item(event) -> dict:
    timestamp = getattr(event, "timestamp", None)
    return {
        "id": str(getattr(event, "id", "") or ""),
        "title": str(getattr(event, "title", "") or "").strip(),
        "summary": str(getattr(event, "summary", "") or "").strip(),
        "source": str(getattr(event, "source", "") or "").strip(),
        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else "",
        "importance": int(getattr(event, "importance", 0) or 0),
        "score": round(float(getattr(event, "final_score", 0.0) or 0.0), 4),
        "tags": [str(tag).strip() for tag in (getattr(event, "tags", []) or []) if str(tag).strip()][:4],
    }


def _event_sort_key(event) -> float:
    timestamp = getattr(event, "timestamp", None)
    if not isinstance(timestamp, datetime):
        return 0.0
    event_utc = timestamp.astimezone(timezone.utc) if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    return event_utc.timestamp()


def _latest_timestamp_iso(events: list) -> str:
    if not events:
        return ""
    latest = max(events, key=_event_sort_key)
    timestamp = getattr(latest, "timestamp", None)
    return timestamp.isoformat() if hasattr(timestamp, "isoformat") else ""


def _age_hours(event) -> float | None:
    timestamp = getattr(event, "timestamp", None)
    if not isinstance(timestamp, datetime):
        return None
    event_utc = timestamp.astimezone(timezone.utc) if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - event_utc).total_seconds() / 3600.0)


def _is_publishable_public_event(event, *, key: str) -> bool:
    rules = dict(_PUBLIC_SECTION_RULES.get(key) or {})
    min_importance = int(rules.get("min_importance") or 1)
    min_score = float(rules.get("min_score") or 0.0)
    max_age_hours = float(rules.get("max_age_hours") or 9999.0)
    importance = int(getattr(event, "importance", 0) or 0)
    score = float(getattr(event, "final_score", 0.0) or 0.0)
    age_hours = _age_hours(event)
    if importance < min_importance:
        return False
    if score < min_score:
        return False
    if age_hours is not None and age_hours > max_age_hours:
        return False
    return True


def _build_public_changed_today(sections: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for section in sections:
        label = str(section.get("label") or section.get("key") or "").strip()
        for item in list(section.get("items") or []):
            rows.append(
                {
                    "section": label,
                    "title": str(item.get("title") or "").strip(),
                    "timestamp": str(item.get("timestamp") or "").strip(),
                    "source": str(item.get("source") or "").strip(),
                    "score": float(item.get("score") or 0.0),
                }
            )
    rows.sort(key=lambda item: (float(item.get("score") or 0.0), str(item.get("timestamp") or "")), reverse=True)
    return rows[:8]
