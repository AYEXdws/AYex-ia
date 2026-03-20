from __future__ import annotations

import json
import re
from datetime import datetime, timezone

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
        timestamp: datetime | None = None,
        tags: list[str] | None = None,
    ) -> IntelEvent | None:
        event = IntelEvent(
            title=title.strip(),
            summary=summary.strip(),
            category=category.strip() or "other",
            importance=max(1, min(10, int(importance))),
            timestamp=timestamp or datetime.utcnow(),
            source=source.strip() or "internal",
            tags=tags or [],
        )
        score = self.calculate_score(event)
        event.importance_score = score["importance_score"]
        event.urgency_score = score["urgency_score"]
        event.confidence_score = score["confidence_score"]
        event.final_score = score["final_score"]
        return self.store.add_event(event)

    def validate_event_payload(self, payload: dict) -> dict:
        allowed_categories = {"economy", "security", "tech", "global", "other"}
        title = str(payload.get("title") or "").strip()
        summary = str(payload.get("summary") or "").strip()
        if len(title) < 5:
            raise ValueError("title_invalid")
        if len(summary) < 10:
            raise ValueError("summary_invalid")

        category = str(payload.get("category") or "other").strip().lower()
        if category not in allowed_categories:
            category = "other"

        importance_raw = payload.get("importance", 5)
        try:
            importance = int(float(importance_raw))
        except (TypeError, ValueError):
            importance = 5
        importance = max(1, min(10, importance))

        tags_raw = payload.get("tags")
        tags: list[str] = []
        if isinstance(tags_raw, list):
            for item in tags_raw:
                val = str(item or "").strip().lower()
                if not val:
                    continue
                tags.append(val[:24])
                if len(tags) >= 5:
                    break

        source = str(payload.get("source") or "unknown").strip() or "unknown"
        ts_raw = payload.get("timestamp")
        ts = datetime.utcnow()
        if isinstance(ts_raw, str) and ts_raw.strip():
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.utcnow()

        return {
            "source": source,
            "type": str(payload.get("type") or "generic").strip() or "generic",
            "title": title,
            "summary": summary,
            "category": category,
            "importance": importance,
            "tags": tags,
            "timestamp": ts,
        }

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
        logger.info("MODEL_SELECTED model=%s mode=%s reason=%s", "gpt-4o-mini", "intel_analysis", "event_analysis")
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

    def should_analyze(self, event: IntelEvent) -> bool:
        if float(event.final_score) < 0.5:
            return False
        if float(event.importance_score) < 0.4:
            return False
        if str(event.category or "").strip().lower() == "low":
            return False
        return True

    def filter_by_user_profile(self, events: list[IntelEvent], user_id: str) -> list[IntelEvent]:
        # Placeholder for future user-specific category/interest filtering.
        _ = user_id
        return list(events)

    def build_insight(self, event: IntelEvent, analysis: dict) -> dict:
        return {
            "title": event.title,
            "summary": event.summary,
            "importance": analysis.get("importance_reason", ""),
            "impact": analysis.get("impact", ""),
            "action": analysis.get("action", "monitor"),
            "score": event.final_score,
            "tags": event.tags,
        }

    def generate_daily_brief(self, insights: list[dict]) -> str:
        if not insights:
            return "No high-priority intelligence insights for today."
        if self.openai_client is None:
            return self._fallback_daily_brief(insights, reason="openai_client_missing")
        logger.info("MODEL_SELECTED model=%s mode=%s reason=%s", "gpt-4o-mini", "intel_brief", "daily_brief_summary")
        prompt = (
            "Summarize the most important global events into a short intelligence brief.\n\n"
            f"Insights: {json.dumps(insights[:3], ensure_ascii=False)}"
        )
        try:
            res = self.openai_client.call_responses(
                prompt=prompt,
                model="gpt-4o-mini",
                instructions="Sharp analytical tone, no fluff, keep it under 120 tokens.",
                max_output_tokens=120,
                route_name="intel_daily_brief",
            )
            text = (res.text or "").strip()
            if not text:
                return self._fallback_daily_brief(insights, reason="empty_model_brief")
            logger.info("DAILY_BRIEF_CREATED source=model length=%s", len(text))
            return text
        except Exception as exc:
            logger.error("INTEL_DAILY_BRIEF_ERROR error=%s", exc)
            return self._fallback_daily_brief(insights, reason="openai_error")

    def get_daily_brief(self, user_id: str = "default") -> dict:
        events = self.store.get_all_events()
        scored = sorted(events, key=lambda e: float(e.final_score), reverse=True)
        user_filtered = self.filter_by_user_profile(scored, user_id=user_id)
        filtered = [e for e in user_filtered if self.should_analyze(e)]
        filtered_out_count = max(0, len(user_filtered) - len(filtered))
        logger.info("FILTERED_OUT_COUNT value=%s", filtered_out_count)
        selected = filtered[:3]
        logger.info("ANALYZED_EVENT_COUNT value=%s", len(selected))

        insights: list[dict] = []
        for event in selected:
            analysis = self.analyze_event(event)
            insights.append(self.build_insight(event, analysis))

        daily_brief = self.generate_daily_brief(insights)
        return {
            "insights": insights,
            "daily_brief": daily_brief,
            "count": len(insights),
            "generated_at": datetime.utcnow().isoformat(),
        }

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

    def _fallback_daily_brief(self, insights: list[dict], reason: str) -> str:
        top = insights[:3]
        bullets = [f"- {item.get('title', 'Event')}: {item.get('action', 'monitor')}" for item in top]
        text = f"Intel brief fallback ({reason}):\n" + "\n".join(bullets)
        logger.info("DAILY_BRIEF_CREATED source=fallback length=%s", len(text))
        return text


def get_intel_summary(service: IntelService, *, user_id: str = "default", max_chars: int = 1400) -> str:
    """Build a compact intel summary string for prompt injection."""
    data = service.get_daily_brief(user_id=user_id)
    if not isinstance(data, dict):
        return ""
    compact = {
        "daily_brief": str(data.get("daily_brief") or "").strip(),
        "insights": data.get("insights") or [],
        "count": data.get("count", 0),
    }
    text = json.dumps(compact, ensure_ascii=False)
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


def build_intel_context(service: IntelService, user_id: str, *, max_events: int = 5) -> dict:
    events = service.store.get_all_events()
    scored = sorted(events, key=lambda e: float(e.final_score), reverse=True)
    filtered = service.filter_by_user_profile(scored, user_id=user_id)

    now_utc = datetime.utcnow()
    ranked_events: list[tuple[float, float, str, IntelEvent]] = []
    for event in filtered:
        ts = event.timestamp
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        age_hours = max(0.0, (now_utc - ts).total_seconds() / 3600.0)
        if age_hours < 6:
            freshness_multiplier = 1.15
            time_window = "<6h"
        elif age_hours < 24:
            freshness_multiplier = 1.08
            time_window = "<24h"
        elif age_hours < 72:
            freshness_multiplier = 1.00
            time_window = "<72h"
        else:
            freshness_multiplier = 0.90
            time_window = ">72h"
        effective_score = float(event.final_score) * freshness_multiplier
        ranked_events.append((effective_score, freshness_multiplier, time_window, event))

    ranked_events.sort(key=lambda x: x[0], reverse=True)

    seen_titles: set[str] = set()
    key_events: list[dict] = []
    time_windows: list[str] = []
    for effective_score, freshness_multiplier, time_window, event in ranked_events:
        normalized = re.sub(r"\s+", " ", str(event.title or "").strip().lower())
        if not normalized or normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        time_windows.append(time_window)
        key_events.append(
            {
                "title": event.title,
                "summary": str(event.summary or "")[:220],
                "category": event.category,
                "score": round(float(event.final_score), 4),
                "effective_score": round(float(effective_score), 4),
                "freshness_multiplier": round(float(freshness_multiplier), 2),
                "importance": int(event.importance),
                "source": event.source,
                "tags": list(event.tags or [])[:4],
                "timestamp": event.timestamp.isoformat(),
            }
        )
        if len(key_events) >= max(3, min(5, max_events)):
            break

    trend_keywords = ("rise", "rises", "surge", "growth", "improves", "record")
    anomaly_keywords = ("breach", "outage", "crash", "urgent", "spike")
    risk_keywords = ("risk", "regulation", "breach", "outage", "volatility", "sanction")
    signals: list[str] = []
    for ev in key_events:
        title_low = str(ev.get("title") or "").lower()
        tags_low = " ".join([str(t).lower() for t in ev.get("tags") or []])
        mixed = f"{title_low} {tags_low}"
        if any(k in mixed for k in trend_keywords):
            signals.append(f"trend:{ev.get('title')}")
        if any(k in mixed for k in anomaly_keywords):
            signals.append(f"anomaly:{ev.get('title')}")
        if any(k in mixed for k in risk_keywords):
            signals.append(f"risk:{ev.get('title')}")
    dedup_signals: list[str] = []
    seen_signals: set[str] = set()
    for signal in signals:
        if signal in seen_signals:
            continue
        seen_signals.add(signal)
        dedup_signals.append(signal)
        if len(dedup_signals) >= 8:
            break

    if key_events:
        summary = " | ".join(
            [f"{item['title']} (score:{item['score']:.2f}, cat:{item['category']})" for item in key_events[:3]]
        )
    else:
        summary = "No high-confidence events available."

    if time_windows:
        dominant_time_window = max(set(time_windows), key=time_windows.count)
    else:
        dominant_time_window = "unknown"

    confidence = 0.0
    if key_events:
        confidence = sum(float(item["effective_score"]) for item in key_events) / float(len(key_events))
        confidence = max(0.0, min(1.0, confidence))

    return {
        "key_events": key_events,
        "summary": summary[:900],
        "signals": dedup_signals,
        "confidence": round(confidence, 4),
        "recency_note": f"dominant_time_window={dominant_time_window}",
    }
