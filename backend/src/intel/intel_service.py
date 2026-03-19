from __future__ import annotations

import json

from backend.src.intel.event_model import IntelEvent
from backend.src.intel.intel_store import IntelStore
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


class IntelService:
    def __init__(self, store: IntelStore, openai_client=None):
        self.store = store
        self.openai_client = openai_client

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
        score = self.calculate_score(event)
        event.importance_score = score["importance_score"]
        event.urgency_score = score["urgency_score"]
        event.confidence_score = score["confidence_score"]
        event.final_score = score["final_score"]
        return self.store.add_event(event)

    def calculate_score(self, event: IntelEvent) -> dict:
        importance_score = max(0.1, min(1.0, float(event.importance) / 10.0))
        title_low = (event.title or "").lower()
        if any(k in title_low for k in ("breach", "crash", "urgent")):
            urgency_score = 0.95
        else:
            urgency_score = 0.6
        confidence_score = 0.7
        final_score = (importance_score * 0.5) + (urgency_score * 0.3) + (confidence_score * 0.2)
        return {
            "importance_score": round(importance_score, 4),
            "urgency_score": round(urgency_score, 4),
            "confidence_score": round(confidence_score, 4),
            "final_score": round(final_score, 4),
        }

    def analyze_event(self, event: IntelEvent) -> dict:
        if self.openai_client is None:
            return self._fallback_analysis(event, reason="openai_client_missing")
        prompt = (
            "Analyze this event:\n"
            "- Why is it important?\n"
            "- What could be the impact?\n"
            "- Should it be monitored?\n\n"
            "Return short structured insight.\n\n"
            f"Title: {event.title}\n"
            f"Summary: {event.summary}\n"
            f"Category: {event.category}\n"
            f"Importance: {event.importance}\n"
            f"Source: {event.source}\n"
            f"Tags: {', '.join(event.tags)}\n\n"
            "Respond as JSON with keys: importance_reason, impact, action."
        )
        try:
            res = self.openai_client.call_responses(
                prompt=prompt,
                model="gpt-4o-mini",
                instructions=(
                    "Keep output concise. action must be either 'monitor' or 'ignore'. "
                    "Return only valid JSON."
                ),
                max_output_tokens=160,
                route_name="intel_analysis",
            )
            parsed = self._parse_analysis_json(res.text)
            if parsed is None:
                return self._fallback_analysis(event, reason="invalid_json_from_model")
            return parsed
        except Exception as exc:
            logger.error("INTEL_ANALYZE_ERROR event_id=%s error=%s", event.id, exc)
            return self._fallback_analysis(event, reason="openai_error")

    def get_daily_brief(self) -> dict:
        top = self.store.get_top_events(limit=3)
        items = [
            {
                "event": {
                    "id": e.id,
                    "title": e.title,
                    "summary": e.summary,
                    "category": e.category,
                    "importance": e.importance,
                    "timestamp": e.timestamp.isoformat(),
                    "source": e.source,
                    "tags": e.tags,
                },
                "score": {
                    "final": e.final_score,
                    "importance": e.importance_score,
                    "urgency": e.urgency_score,
                },
                "analysis": self.analyze_event(e),
            }
            for e in top
        ]
        return {"top_events": items, "count": len(self.store.get_all_events())}

    def _parse_analysis_json(self, text: str) -> dict | None:
        raw = (text or "").strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                data = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return None
        if not isinstance(data, dict):
            return None
        importance_reason = str(data.get("importance_reason") or "").strip()
        impact = str(data.get("impact") or "").strip()
        action = str(data.get("action") or "").strip().lower()
        if action not in {"monitor", "ignore"}:
            action = "monitor"
        if not importance_reason or not impact:
            return None
        return {
            "importance_reason": importance_reason[:280],
            "impact": impact[:280],
            "action": action,
        }

    def _fallback_analysis(self, event: IntelEvent, reason: str) -> dict:
        action = "monitor" if int(event.importance) >= 7 else "ignore"
        return {
            "importance_reason": f"Auto-analysis fallback ({reason}): event importance={event.importance}.",
            "impact": "Potential impact exists; manual review recommended.",
            "action": action,
        }
