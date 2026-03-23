from __future__ import annotations

from datetime import datetime
from typing import Any


def build_recent_decisions(chat_store: Any, *, limit: int = 6, sessions_window: int = 18) -> list[dict[str, Any]]:
    if not chat_store:
        return []

    try:
        sessions = list(chat_store.list_sessions(limit=max(1, min(60, sessions_window))) or [])
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for session in sessions:
        session_id = str(session.get("id") or "").strip()
        session_title = str(session.get("title") or "Oturum").strip() or "Oturum"
        if not session_id:
            continue
        try:
            messages = list(chat_store.messages(session_id, limit=80) or [])
        except Exception:
            continue
        for message in reversed(messages):
            row = _decision_row(message=message, session_id=session_id, session_title=session_title)
            if not row:
                continue
            dedupe_key = f"{row['session_id']}|{row['summary'][:80]}|{row['asset']}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(row)
            if len(rows) >= max(1, min(20, limit * 2)):
                break

    rows.sort(key=lambda item: item.get("_sort_ts", ""), reverse=True)
    out: list[dict[str, Any]] = []
    for item in rows[: max(1, min(20, limit))]:
        clean = dict(item)
        clean.pop("_sort_ts", None)
        out.append(clean)
    return out


def _decision_row(*, message: dict[str, Any], session_id: str, session_title: str) -> dict[str, Any] | None:
    if str(message.get("role") or "").strip().lower() != "assistant":
        return None

    metrics = dict(message.get("metrics") or {})
    trace = dict(metrics.get("explainability") or {})
    response_mode = str(trace.get("response_mode") or metrics.get("response_mode") or "").strip().lower()
    decision_summary = str(trace.get("decision") or "").strip()
    asset = str(trace.get("decision_asset") or "").strip().upper()
    stance = str(trace.get("decision_stance") or "").strip().lower()
    if response_mode != "decision" and not decision_summary and not asset:
        return None

    ts = str(message.get("ts") or "").strip()
    iso_ts = _normalize_ts(ts)
    text = str(message.get("text") or "").strip()
    reasons = [str(item).strip() for item in (trace.get("reasons") or []) if str(item).strip()][:2]
    risks = [str(item).strip() for item in (trace.get("risks") or []) if str(item).strip()][:1]

    return {
        "session_id": session_id,
        "session_title": session_title,
        "timestamp": iso_ts,
        "response_mode": response_mode or "decision",
        "asset": asset,
        "stance": stance or "watch",
        "summary": decision_summary or _fallback_summary(text),
        "reasons": reasons,
        "risks": risks,
        "source": str(metrics.get("source") or "").strip(),
        "_sort_ts": iso_ts or "",
    }


def _normalize_ts(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw).isoformat()
    except ValueError:
        return raw


def _fallback_summary(text: str) -> str:
    first = str(text or "").strip().splitlines()
    return first[0].strip()[:220] if first else ""
