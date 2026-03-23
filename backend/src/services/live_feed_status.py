from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def freshness_meta(ts) -> tuple[str, str, float | None]:
    if not isinstance(ts, datetime):
        return "unknown", "unknown", None
    event_utc = ts.astimezone(timezone.utc) if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (datetime.now(timezone.utc) - event_utc).total_seconds() / 3600.0)
    if age_hours < 2:
        return "<2h", "fresh", age_hours
    if age_hours < 6:
        return "<6h", "fresh", age_hours
    if age_hours < 12:
        return "<12h", "watch", age_hours
    if age_hours < 24:
        return "12h+", "stale", age_hours
    if age_hours < 72:
        return "24h+", "stale", age_hours
    return "72h+", "old", age_hours


def build_source_focus(
    latest_events: list[Any],
    *,
    label: str,
    sources: set[str],
    fallback: str,
) -> dict[str, Any]:
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
            "label": label,
            "available": False,
            "active": False,
            "summary": fallback,
            "signal": "unknown",
            "reasons": [],
            "freshness": "unknown",
            "freshness_state": "unknown",
            "source": "",
            "latest_at": "",
            "age_hours": None,
        }

    ts = getattr(event, "timestamp", None)
    freshness, freshness_state, age_hours = freshness_meta(ts)
    summary = str(getattr(event, "title", "") or "").strip() or fallback
    detail = str(getattr(event, "summary", "") or "").strip()
    reasons = [f"Tazelik: {freshness}"]
    if detail:
        reasons.append(detail[:220])
    return {
        "label": label,
        "available": True,
        "active": freshness_state == "fresh",
        "summary": summary,
        "signal": freshness_state,
        "reasons": reasons[:2],
        "freshness": freshness,
        "freshness_state": freshness_state,
        "source": str(getattr(event, "source", "") or "").strip(),
        "latest_at": ts.isoformat() if hasattr(ts, "isoformat") else "",
        "age_hours": round(float(age_hours), 2) if age_hours is not None else None,
    }


def build_live_inventory(latest_events: list[Any]) -> dict[str, Any]:
    feeds = {
        "crypto": build_source_focus(
            latest_events,
            label="Kripto",
            sources={"coingecko"},
            fallback="Kripto feed'inde taze event yok.",
        ),
        "equities": build_source_focus(
            latest_events,
            label="Hisse",
            sources={"yahoo_finance"},
            fallback="Hisse feed'inde taze event yok.",
        ),
        "macro": build_source_focus(
            latest_events,
            label="Makro",
            sources={"er_api"},
            fallback="Makro feed'inde taze event yok.",
        ),
        "world": build_source_focus(
            latest_events,
            label="World",
            sources={"bbc_world", "reuters"},
            fallback="World feed'inde taze event yok.",
        ),
        "cyber": build_source_focus(
            latest_events,
            label="Cyber",
            sources={"the_hacker_news"},
            fallback="Cyber feed'inde taze event yok.",
        ),
    }
    return {
        "feeds": feeds,
        "active_count": sum(1 for row in feeds.values() if row.get("active")),
        "available_count": sum(1 for row in feeds.values() if row.get("available")),
    }


def render_live_inventory_reply(latest_events: list[Any]) -> str:
    inventory = build_live_inventory(latest_events)
    lines = ["Su an gordugum canli veri yuzeyi soyle:"]
    for key in ("crypto", "equities", "macro", "world", "cyber"):
        row = dict(inventory["feeds"].get(key) or {})
        label = str(row.get("label") or key).strip()
        if not row.get("available"):
            lines.append(f"{label}: veri yok.")
            continue
        freshness = str(row.get("freshness") or "unknown")
        summary = str(row.get("summary") or "").strip()
        state = str(row.get("freshness_state") or "unknown")
        if state == "fresh":
            prefix = f"{label}: aktif ({freshness})."
        elif state == "watch":
            prefix = f"{label}: var ama tazeligi sinirda ({freshness})."
        else:
            prefix = f"{label}: veri var ama bayat ({freshness})."
        lines.append(f"{prefix} Son sinyal: {summary}" if summary else prefix)
    return "\n".join(lines).strip()
