from __future__ import annotations

import json
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path
import threading

from backend.src.intel.event_model import IntelEvent


class IntelStore:
    def __init__(self, persist_path: str | Path | None = None):
        self._events: list[IntelEvent] = []
        self._lock = threading.Lock()
        self._persist_path: Path | None = Path(persist_path).expanduser().resolve() if persist_path else None
        if self._persist_path is not None:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            if self._persist_path.exists():
                self._load_from_disk()
            else:
                self._persist_path.write_text("[]", encoding="utf-8")

    def add_event(self, event: IntelEvent) -> IntelEvent | None:
        with self._lock:
            if self._is_duplicate_title(event.title):
                return None
            self._events.append(event)
            self._persist_to_disk()
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
                key=lambda x: x.timestamp or datetime.min,
                reverse=True,
            )
            return ordered[: max(1, min(100, limit))]

    def _is_duplicate_title(self, title: str) -> bool:
        normalized = (title or "").strip().lower()
        if not normalized:
            return True
        recent = self._events[-20:]
        for ev in recent:
            existing = (ev.title or "").strip().lower()
            if not existing:
                continue
            ratio = SequenceMatcher(None, normalized, existing).ratio() * 100.0
            if ratio > 90.0:
                return True
        return False

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
            loaded.append(IntelEvent(**event_kwargs))
        self._events = loaded

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
