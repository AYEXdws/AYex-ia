from __future__ import annotations

import json
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading

from backend.src.intel.intel_archive import IntelArchive
from backend.src.intel.event_model import IntelEvent
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


class IntelStore:
    def __init__(self, persist_path: str | Path | None = None, archive: IntelArchive | None = None):
        self._events: list[IntelEvent] = []
        self._lock = threading.Lock()
        self.archive = archive
        self._persist_path: Path | None = Path(persist_path).expanduser().resolve() if persist_path else None
        if self._persist_path is not None:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            if self._persist_path.exists():
                self._load_from_disk()
            else:
                self._persist_path.write_text("[]", encoding="utf-8")
            self._restore_from_archive_if_empty()

    def add_event(self, event: IntelEvent) -> IntelEvent | None:
        with self._lock:
            if self._is_duplicate_title(event.title, incoming_event=event):
                return None
            self._events.append(event)
            self._persist_to_disk()
            if self.archive is not None:
                try:
                    self.archive.archive_event(event)
                except Exception as exc:
                    logger.info("INTEL_ARCHIVE_WRITE_FAIL error=%s", exc)
            return event

    def get_all_events(self) -> list[IntelEvent]:
        with self._lock:
            return list(self._events)

    def get_top_events(self, limit: int = 5) -> list[IntelEvent]:
        with self._lock:
            ordered = sorted(self._events, key=lambda x: float(x.final_score), reverse=True)
            return ordered[: max(1, min(100, limit))]

    def get_latest_events(self, limit: int = 10) -> list[IntelEvent]:
        with self._lock:
            ordered = sorted(
                self._events,
                key=lambda x: self._normalize_sort_timestamp(getattr(x, "timestamp", None)),
                reverse=True,
            )
            return ordered[: max(1, min(100, limit))]

    def _normalize_sort_timestamp(self, ts) -> datetime:
        if not isinstance(ts, datetime):
            return datetime.min
        if ts.tzinfo is not None:
            try:
                return ts.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                return datetime.min
        return ts

    def _is_duplicate_title(self, title: str, incoming_event: IntelEvent | None = None) -> bool:
        normalized = (title or "").strip().lower()
        if not normalized:
            return True
        recent = self._events[-20:]
        if incoming_event is not None and self._is_market_like(incoming_event):
            now_utc = datetime.utcnow()
            recent = []
            for ev in self._events:
                ev_ts = self._normalize_sort_timestamp(getattr(ev, "timestamp", None))
                if ev_ts == datetime.min:
                    continue
                age_seconds = (now_utc - ev_ts).total_seconds()
                if 0.0 <= age_seconds <= 3600.0:
                    recent.append(ev)
        for ev in recent:
            existing = (ev.title or "").strip().lower()
            if not existing:
                continue
            ratio = SequenceMatcher(None, normalized, existing).ratio() * 100.0
            if ratio > 90.0:
                return True
        return False

    def _is_market_like(self, event: IntelEvent) -> bool:
        category = str(getattr(event, "category", "") or "").strip().lower()
        source_type = str(getattr(event, "source_type", "") or "").strip().lower()
        source = str(getattr(event, "source", "") or "").strip().lower()
        return category == "economy" or source_type == "market_api" or source == "market_api"

    def _load_from_disk(self) -> None:
        if self._persist_path is None:
            return
        try:
            raw = json.loads(self._persist_path.read_text(encoding="utf-8"))
        except Exception:
            raw = []
        if not isinstance(raw, list):
            raw = []
        loaded: list[IntelEvent] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            loaded.append(self._event_from_dict(item))
        self._events = loaded

    def _restore_from_archive_if_empty(self) -> None:
        if self._events:
            return
        today = datetime.utcnow().date()
        candidate_days = [today, today - timedelta(days=1)]
        for day in candidate_days:
            day_str = day.isoformat()
            restored = self._load_archive_day(day_str)
            if not restored:
                continue
            self._events = restored
            self._persist_to_disk()
            logger.info("INTEL_STORE_RESTORED_FROM_ARCHIVE date=%s count=%s", day_str, len(restored))
            return

    def _load_archive_day(self, date_str: str) -> list[IntelEvent]:
        if self.archive is not None:
            try:
                restored = list(self.archive.get_events_by_date(date_str) or [])
                return restored
            except Exception as exc:
                logger.info("INTEL_ARCHIVE_RESTORE_FAIL date=%s error=%s", date_str, exc)
                return []
        if self._persist_path is None:
            return []
        archive_path = self._persist_path.parent / "archive" / f"{date_str}.json"
        if not archive_path.exists():
            return []
        try:
            raw = json.loads(archive_path.read_text(encoding="utf-8"))
        except Exception:
            raw = []
        if not isinstance(raw, list):
            return []
        out: list[IntelEvent] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            out.append(self._event_from_dict(item))
        return out

    def _event_from_dict(self, item: dict) -> IntelEvent:
        ts_raw = item.get("timestamp")
        ts = datetime.utcnow()
        if isinstance(ts_raw, str) and ts_raw.strip():
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.utcnow()
        event_kwargs = {
            "title": str(item.get("title") or ""),
            "summary": str(item.get("summary") or ""),
            "category": str(item.get("category") or "other"),
            "importance": max(1, min(10, int(item.get("importance", 5) or 5))),
            "timestamp": ts,
            "source": str(item.get("source") or "internal"),
            "tags": [str(x) for x in (item.get("tags") or []) if str(x).strip()],
            "importance_score": float(item.get("importance_score", 0.0) or 0.0),
            "urgency_score": float(item.get("urgency_score", 0.0) or 0.0),
            "confidence_score": float(item.get("confidence_score", 0.0) or 0.0),
            "final_score": float(item.get("final_score", 0.0) or 0.0),
        }
        event_id = str(item.get("id") or "").strip()
        if event_id:
            event_kwargs["id"] = event_id
        return IntelEvent(**event_kwargs)

    def _persist_to_disk(self) -> None:
        if self._persist_path is None:
            return
        rows = [self._serialize_event(ev) for ev in self._events]
        tmp = self._persist_path.with_suffix(self._persist_path.suffix + ".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._persist_path)

    def _serialize_event(self, event: IntelEvent) -> dict:
        return {
            "id": event.id,
            "title": event.title,
            "summary": event.summary,
            "category": event.category,
            "importance": int(event.importance),
            "timestamp": event.timestamp.isoformat(),
            "source": event.source,
            "tags": list(event.tags or []),
            "importance_score": float(event.importance_score),
            "urgency_score": float(event.urgency_score),
            "confidence_score": float(event.confidence_score),
            "final_score": float(event.final_score),
        }
