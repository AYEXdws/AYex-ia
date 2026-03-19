from __future__ import annotations

from backend.src.intel.event_model import IntelEvent
from backend.src.intel.intel_store import IntelStore


class IntelService:
    def __init__(self, store: IntelStore):
        self.store = store

    def create_event(
        self,
        *,
        title: str,
        summary: str,
        category: str,
        importance: int,
        source: str,
        tags: list[str] | None = None,
    ) -> IntelEvent:
        event = IntelEvent(
            title=title.strip(),
            summary=summary.strip(),
            category=category.strip() or "general",
            importance=max(1, min(10, int(importance))),
            source=source.strip() or "internal",
            tags=tags or [],
        )
        return self.store.add_event(event)

    def get_daily_brief(self) -> dict:
        top = self.store.get_top_events(limit=5)
        items = [
            {
                "id": e.id,
                "title": e.title,
                "summary": e.summary,
                "category": e.category,
                "importance": e.importance,
                "timestamp": e.timestamp.isoformat(),
                "source": e.source,
                "tags": e.tags,
            }
            for e in top
        ]
        return {"top_events": items, "count": len(self.store.get_all_events())}
