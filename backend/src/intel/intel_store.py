from __future__ import annotations

from backend.src.intel.event_model import IntelEvent


class IntelStore:
    def __init__(self):
        self._events: list[IntelEvent] = []

    def add_event(self, event: IntelEvent) -> IntelEvent:
        self._events.append(event)
        return event

    def get_all_events(self) -> list[IntelEvent]:
        return list(self._events)

    def get_top_events(self, limit: int = 5) -> list[IntelEvent]:
        ordered = sorted(self._events, key=lambda x: float(x.final_score), reverse=True)
        return ordered[: max(1, min(100, limit))]
