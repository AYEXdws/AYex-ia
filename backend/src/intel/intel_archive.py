from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend.src.intel.event_model import IntelEvent


class IntelArchive:
    """
    Stores daily snapshots of intel events.
    Structure: .ayex/archive/YYYY-MM-DD.json
    Each file contains all events from that day.
    """

    def __init__(self, data_dir: str | Path):
        self.archive_dir = Path(data_dir).expanduser().resolve() / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def archive_event(self, event: IntelEvent):
        ts = self._to_utc_datetime(getattr(event, "timestamp", None))
        day_str = ts.date().isoformat()
        path = self._day_path(day_str)
        rows = self._read_rows(path)
        event_row = self._serialize_event(event)
        event_id = str(event_row.get("id") or "").strip()
        if event_id and any(str(item.get("id") or "").strip() == event_id for item in rows):
            return
        rows.append(event_row)
        self._write_rows(path, rows)

    def get_events_by_date(self, date: str) -> list[IntelEvent]:
        path = self._day_path(date)
        rows = self._read_rows(path)
        return [self._deserialize_event(row) for row in rows if isinstance(row, dict)]

    def get_events_by_range(self, start: str, end: str) -> list[IntelEvent]:
        start_date = self._parse_date(start)
        end_date = self._parse_date(end)
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        out: list[IntelEvent] = []
        day = start_date
        while day <= end_date:
            out.extend(self.get_events_by_date(day.isoformat()))
            day += timedelta(days=1)
        out.sort(key=lambda ev: self._to_utc_datetime(getattr(ev, "timestamp", None)), reverse=True)
        return out

    def get_yesterday_events(self) -> list[IntelEvent]:
        day = datetime.utcnow().date() - timedelta(days=1)
        return self.get_events_by_date(day.isoformat())

    def get_today_events(self) -> list[IntelEvent]:
        day = datetime.utcnow().date()
        return self.get_events_by_date(day.isoformat())

    def get_latest_by_category(self, category: str, date: str = None) -> dict:
        target_date = date or datetime.utcnow().date().isoformat()
        events = self.get_events_by_date(target_date)
        cat = str(category or "").strip().lower()
        filtered = [ev for ev in events if str(getattr(ev, "category", "") or "").strip().lower() == cat]
        if not filtered:
            return {}
        filtered.sort(key=lambda ev: self._to_utc_datetime(getattr(ev, "timestamp", None)), reverse=True)
        return self._serialize_event(filtered[0])

    def _day_path(self, date_str: str) -> Path:
        return self.archive_dir / f"{date_str}.json"

    def _parse_date(self, value: str) -> date:
        return datetime.strptime(value, "%Y-%m-%d").date()

    def _read_rows(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = []
        return data if isinstance(data, list) else []

    def _write_rows(self, path: Path, rows: list[dict]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _to_utc_datetime(self, ts) -> datetime:
        if isinstance(ts, datetime):
            if ts.tzinfo is not None:
                return ts.astimezone(timezone.utc).replace(tzinfo=None)
            return ts
        return datetime.utcnow()

    def _serialize_event(self, event: IntelEvent) -> dict:
        ts = self._to_utc_datetime(getattr(event, "timestamp", None))
        return {
            "id": str(getattr(event, "id", "") or ""),
            "title": str(getattr(event, "title", "") or ""),
            "summary": str(getattr(event, "summary", "") or ""),
            "category": str(getattr(event, "category", "other") or "other"),
            "importance": int(getattr(event, "importance", 5) or 5),
            "timestamp": ts.isoformat(),
            "source": str(getattr(event, "source", "internal") or "internal"),
            "tags": list(getattr(event, "tags", []) or []),
            "importance_score": float(getattr(event, "importance_score", 0.0) or 0.0),
            "urgency_score": float(getattr(event, "urgency_score", 0.0) or 0.0),
            "confidence_score": float(getattr(event, "confidence_score", 0.0) or 0.0),
            "final_score": float(getattr(event, "final_score", 0.0) or 0.0),
        }

    def _deserialize_event(self, row: dict) -> IntelEvent:
        ts_raw = row.get("timestamp")
        ts = datetime.utcnow()
        if isinstance(ts_raw, str) and ts_raw.strip():
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.utcnow()
        kwargs = {
            "title": str(row.get("title") or ""),
            "summary": str(row.get("summary") or ""),
            "category": str(row.get("category") or "other"),
            "importance": max(1, min(10, int(row.get("importance", 5) or 5))),
            "timestamp": ts,
            "source": str(row.get("source") or "internal"),
            "tags": [str(x) for x in (row.get("tags") or []) if str(x).strip()],
            "importance_score": float(row.get("importance_score", 0.0) or 0.0),
            "urgency_score": float(row.get("urgency_score", 0.0) or 0.0),
            "confidence_score": float(row.get("confidence_score", 0.0) or 0.0),
            "final_score": float(row.get("final_score", 0.0) or 0.0),
        }
        event_id = str(row.get("id") or "").strip()
        if event_id:
            kwargs["id"] = event_id
        return IntelEvent(**kwargs)
