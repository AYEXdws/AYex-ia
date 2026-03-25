from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def freshness_meta(ts, *, fresh_hours: float = 2.0, watch_hours: float = 12.0, stale_hours: float = 24.0) -> tuple[str, str, float | None]:
    if not isinstance(ts, datetime):
        return "unknown", "unknown", None
    event_utc = ts.astimezone(timezone.utc) if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (datetime.now(timezone.utc) - event_utc).total_seconds() / 3600.0)
    fresh_label = f"<{int(fresh_hours)}h"
    watch_label = f"<{int(watch_hours)}h"
    stale_label = f"{int(watch_hours)}h+"
    old_label = f"{int(stale_hours)}h+"
    if age_hours < fresh_hours:
        return fresh_label, "fresh", age_hours
    if age_hours < max(fresh_hours, 6.0):
        return "<6h", "fresh", age_hours
    if age_hours < watch_hours:
        return watch_label, "watch", age_hours
    if age_hours < stale_hours:
        return stale_label, "stale", age_hours
    if age_hours < 72:
        return old_label, "stale", age_hours
    return "72h+", "old", age_hours


def _timestamp_sort_key(item: Any) -> float:
    ts = getattr(item, "timestamp", None)
    if not isinstance(ts, datetime):
        return 0.0
    event_utc = ts.astimezone(timezone.utc) if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return event_utc.timestamp()


def build_source_focus(
    events: list[Any],
    *,
    label: str,
    sources: set[str],
    fallback: str,
    fresh_hours: float = 2.0,
    watch_hours: float = 12.0,
    stale_hours: float = 24.0,
) -> dict[str, Any]:
    matching = [
        item
        for item in list(events or [])
        if str(getattr(item, "source", "") or "").strip().lower() in sources
    ]
    event = max(matching, key=_timestamp_sort_key, default=None)
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
            "count_24h": 0,
        }

    ts = getattr(event, "timestamp", None)
    freshness, freshness_state, age_hours = freshness_meta(
        ts,
        fresh_hours=fresh_hours,
        watch_hours=watch_hours,
        stale_hours=stale_hours,
    )
    summary = str(getattr(event, "title", "") or "").strip() or fallback
    detail = str(getattr(event, "summary", "") or "").strip()
    reasons = [f"Tazelik: {freshness}"]
    recent_count = 0
    now = datetime.now(timezone.utc)
    for item in matching:
        item_ts = getattr(item, "timestamp", None)
        if not isinstance(item_ts, datetime):
            continue
        item_utc = item_ts.astimezone(timezone.utc) if item_ts.tzinfo is not None else item_ts.replace(tzinfo=timezone.utc)
        age = max(0.0, (now - item_utc).total_seconds() / 3600.0)
        if age <= 24.0:
            recent_count += 1
    reasons.append(f"Son 24 saatte {recent_count} event var.")
    if detail:
        reasons.append(detail[:220])
    return {
        "label": label,
        "available": True,
        "active": freshness_state in {"fresh", "watch"},
        "summary": summary,
        "signal": freshness_state,
        "reasons": reasons[:3],
        "freshness": freshness,
        "freshness_state": freshness_state,
        "source": str(getattr(event, "source", "") or "").strip(),
        "latest_at": ts.isoformat() if hasattr(ts, "isoformat") else "",
        "age_hours": round(float(age_hours), 2) if age_hours is not None else None,
        "count_24h": recent_count,
    }


def build_live_inventory(events: list[Any]) -> dict[str, Any]:
    feeds = {
        "crypto": build_source_focus(
            events,
            label="Kripto",
            sources={"coingecko"},
            fallback="Kripto feed'inde taze event yok.",
            fresh_hours=3.0,
            watch_hours=12.0,
            stale_hours=24.0,
        ),
        "equities": build_source_focus(
            events,
            label="Hisse",
            sources={"yahoo_finance"},
            fallback="Hisse feed'inde taze event yok.",
            fresh_hours=3.0,
            watch_hours=12.0,
            stale_hours=24.0,
        ),
        "macro": build_source_focus(
            events,
            label="Makro",
            sources={"er_api"},
            fallback="Makro feed'inde taze event yok.",
            fresh_hours=4.0,
            watch_hours=24.0,
            stale_hours=48.0,
        ),
        "world": build_source_focus(
            events,
            label="World",
            sources={"bbc_world", "reuters"},
            fallback="World feed'inde taze event yok.",
            fresh_hours=6.0,
            watch_hours=24.0,
            stale_hours=48.0,
        ),
        "cyber": build_source_focus(
            events,
            label="Cyber",
            sources={"the_hacker_news", "bleeping_computer", "dark_reading"},
            fallback="Cyber feed'inde taze event yok.",
            fresh_hours=12.0,
            watch_hours=36.0,
            stale_hours=72.0,
        ),
    }
    return {
        "feeds": feeds,
        "active_count": sum(1 for row in feeds.values() if row.get("active")),
        "available_count": sum(1 for row in feeds.values() if row.get("available")),
    }


def build_feed_health(events: list[Any]) -> dict[str, Any]:
    inventory = build_live_inventory(events)
    feeds = dict(inventory.get("feeds") or {})
    policy = {
        "crypto": {"healthy": 3.0, "warning": 12.0},
        "equities": {"healthy": 3.0, "warning": 12.0},
        "macro": {"healthy": 6.0, "warning": 24.0},
        "world": {"healthy": 12.0, "warning": 48.0},
        "cyber": {"healthy": 18.0, "warning": 72.0},
    }
    rows: dict[str, Any] = {}
    counts = {"healthy": 0, "warning": 0, "down": 0}
    stale_feeds: list[str] = []
    for key, row in feeds.items():
        age_hours = row.get("age_hours")
        spec = policy.get(key, {"healthy": 6.0, "warning": 24.0})
        state = "down"
        reason = "Veri yok."
        if row.get("available") and isinstance(age_hours, (int, float)):
            if age_hours <= spec["healthy"]:
                state = "healthy"
                reason = f"Taze veri akisi var ({row.get('freshness')})."
            elif age_hours <= spec["warning"]:
                state = "warning"
                reason = f"Veri akisi yavasladi ({row.get('freshness')})."
            else:
                state = "down"
                reason = f"Feed bayat kaldi ({row.get('freshness')})."
        label = str(row.get("label") or key).strip()
        counts[state] += 1
        if state != "healthy":
            stale_feeds.append(label)
        rows[key] = {
            "label": label,
            "state": state,
            "reason": reason,
            "freshness": row.get("freshness") or "unknown",
            "count_24h": int(row.get("count_24h") or 0),
            "latest_at": row.get("latest_at") or "",
            "source": row.get("source") or "",
        }
    summary = "Tum feed'ler saglikli."
    if counts["down"]:
        summary = f"{counts['down']} feed durmus veya bayat."
    elif counts["warning"]:
        summary = f"{counts['warning']} feed izlenmeli."
    return {
        "summary": summary,
        "healthy_count": counts["healthy"],
        "warning_count": counts["warning"],
        "down_count": counts["down"],
        "stale_feeds": stale_feeds[:5],
        "feeds": rows,
    }


def render_live_inventory_reply(events: list[Any]) -> str:
    inventory = build_live_inventory(events)
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
