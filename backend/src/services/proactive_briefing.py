from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def build_proactive_briefing(intel_service: Any, *, user_id: str = "default", limit: int = 6) -> dict[str, Any]:
    latest_events = []
    try:
        latest_events = list(getattr(intel_service, "get_latest_events")(limit=max(3, min(12, int(limit or 6)))) or [])
    except Exception:
        latest_events = []

    daily_brief = ""
    insights = []
    try:
        daily = getattr(intel_service, "get_daily_brief")(user_id=user_id) or {}
        daily_brief = str(daily.get("daily_brief") or "").strip()
        insights = list(daily.get("insights") or [])[:4]
    except Exception:
        daily_brief = ""
        insights = []

    priorities: list[str] = []
    watchlist: list[str] = []
    updated_at = ""
    last_day = 0
    previous_window = 0
    categories_last_day: dict[str, int] = {}

    now = datetime.utcnow()
    for event in latest_events:
        title = str(getattr(event, "title", "") or "").strip()
        if title and len(priorities) < 3:
            priorities.append(title)
        ts = getattr(event, "timestamp", None)
        if hasattr(ts, "isoformat"):
            updated_at = max(updated_at, ts.isoformat())
        cat = str(getattr(event, "category", "other") or "other").strip().lower()
        tags = [str(tag).upper() for tag in (getattr(event, "tags", []) or []) if str(tag).strip()]
        if tags:
            for tag in tags[:3]:
                if tag not in watchlist:
                    watchlist.append(tag)
                if len(watchlist) >= 4:
                    break
        if not isinstance(ts, datetime):
            continue
        if ts.tzinfo is not None:
            ts = ts.astimezone().replace(tzinfo=None)
        age_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
        if age_hours <= 24:
            last_day += 1
            categories_last_day[cat] = categories_last_day.get(cat, 0) + 1
        elif age_hours <= 72:
            previous_window += 1

    dominant_category = ""
    if categories_last_day:
        dominant_category = max(categories_last_day, key=categories_last_day.get)

    compare_line = ""
    if last_day or previous_window:
        direction = "arti" if last_day >= previous_window else "daha sakin"
        compare_line = (
            f"Son 24 saatte {last_day} yeni event var. Onceki 24-72 saat penceresine gore akış {direction}."
        )
        if dominant_category:
            compare_line += f" Agirlik merkezi su an {dominant_category}."

    headline = priorities[0] if priorities else "Takip edilmesi gereken yeni bir baskin event yok."
    summary_parts = [part for part in (compare_line, daily_brief[:900]) if part]
    summary = "\n\n".join(summary_parts).strip()

    if not watchlist:
        for item in insights:
            title = str(item.get("title") or "").strip()
            if title and title not in watchlist:
                watchlist.append(title[:32])
            if len(watchlist) >= 4:
                break

    return {
        "headline": headline,
        "summary": summary,
        "compare_line": compare_line,
        "priorities": priorities,
        "watchlist": watchlist[:4],
        "updated_at": updated_at,
        "count_24h": last_day,
        "count_prev_24_72h": previous_window,
    }
