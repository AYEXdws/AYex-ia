from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.src.services.market_decision import CRYPTO_ASSETS, EQUITY_ASSETS, build_asset_signal_board


def build_recent_decisions(
    chat_store: Any,
    *,
    latest_events: list[Any] | None = None,
    profile_data: dict[str, Any] | None = None,
    limit: int = 6,
    sessions_window: int = 18,
) -> list[dict[str, Any]]:
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

    signal_map = _build_current_signal_map(latest_events=latest_events, profile_data=profile_data)
    rows.sort(key=lambda item: item.get("_sort_ts", ""), reverse=True)
    out: list[dict[str, Any]] = []
    for item in rows[: max(1, min(20, limit))]:
        clean = dict(item)
        clean.pop("_sort_ts", None)
        age_status = str(clean.get("age_status") or "unknown").strip() or "unknown"
        outcome_status, outcome_note = _evaluate_outcome(clean, signal_map)
        clean["outcome_status"] = outcome_status
        clean["outcome_note"] = outcome_note
        clean["status"] = outcome_status if outcome_status != "unknown" else age_status
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
        "age_label": _age_label(iso_ts),
        "age_status": _status_for_decision(iso_ts),
        "status": _status_for_decision(iso_ts),
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


def _age_label(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown"
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return "unknown"
    age_hours = max(0.0, (datetime.now() - ts).total_seconds() / 3600.0)
    if age_hours < 6:
        return "<6h"
    if age_hours < 24:
        return "<24h"
    if age_hours < 72:
        return "<72h"
    return "72h+"


def _status_for_decision(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown"
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return "unknown"
    age_hours = max(0.0, (datetime.now() - ts).total_seconds() / 3600.0)
    if age_hours < 72:
        return "beklemede"
    if age_hours < 168:
        return "izlenmeli"
    return "arsiv"


def _build_current_signal_map(*, latest_events: list[Any] | None, profile_data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    latest_events = list(latest_events or [])
    profile_data = dict(profile_data or {})
    rows: dict[str, dict[str, Any]] = {}
    for query in ("1 ay icin hangi coin daha mantikli", "1 ay icin hangi hisse daha mantikli"):
        for row in build_asset_signal_board(
            text=query,
            latest_events=latest_events,
            profile_data=profile_data,
            limit=6,
        ):
            asset = str(row.get("asset") or "").strip().upper()
            if asset:
                rows[asset] = dict(row)
    return rows


def _evaluate_outcome(row: dict[str, Any], signal_map: dict[str, dict[str, Any]]) -> tuple[str, str]:
    asset = str(row.get("asset") or "").strip().upper()
    if not asset:
        return "unknown", ""
    age_status = str(row.get("age_status") or "unknown").strip() or "unknown"
    signal = dict(signal_map.get(asset) or {})
    if not signal:
        if age_status == "beklemede":
            return "beklemede", "Bu asset icin bugun yeterli taze sinyal yok."
        return "sinyal-yok", "Bu asset bugunku sinyal panosunda one cikmiyor."

    current_stance = str(signal.get("stance") or "").strip().lower()
    current_summary = str(signal.get("summary") or "").strip()
    if current_stance == "buy":
        return "gucleniyor", current_summary or f"{asset} bugun de guclu kalmaya devam ediyor."
    if current_stance == "watch":
        return "izlenmeli", current_summary or f"{asset} tamamen bozulmadi, ama teyit gerekiyor."
    if current_stance == "avoid":
        return "zayifladi", current_summary or f"{asset} artik net edge tasimiyor."

    if asset in CRYPTO_ASSETS | EQUITY_ASSETS:
        return "beklemede", current_summary or f"{asset} icin karar baglami hala izleme asamasinda."
    return "unknown", current_summary
