from __future__ import annotations

from difflib import SequenceMatcher

from backend.src.intel.event_model import IntelEvent


class IntelStore:
    def __init__(self):
        self._events: list[IntelEvent] = []

    def add_event(self, event: IntelEvent) -> IntelEvent | None:
        if self._is_duplicate_title(event.title):
            return None
        self._events.append(event)
        return event

    def get_all_events(self) -> list[IntelEvent]:
        return list(self._events)

    def get_top_events(self, limit: int = 5) -> list[IntelEvent]:
        ordered = sorted(self._events, key=lambda x: float(x.final_score), reverse=True)
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
