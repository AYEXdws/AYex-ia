from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Callable

from backend.src.intel.event_model import IntelEvent
from backend.src.intel.intel_store import IntelStore
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


def _normalize_text(text: str) -> str:
    low = (text or "").lower().replace("i̇", "i").replace("\u0307", "")
    table = str.maketrans(
        {
            "ç": "c",
            "ğ": "g",
            "ı": "i",
            "İ": "i",
            "ö": "o",
            "ş": "s",
            "ü": "u",
        }
    )
    return low.translate(table)


def _tokenize(text: str) -> set[str]:
    stopwords = {
        "neden",
        "durum",
        "nasil",
        "hangi",
        "neydi",
        "oluyor",
        "son",
        "guncel",
        "nedir",
        "what",
        "when",
        "where",
    }
    return {
        t
        for t in re.findall(r"[a-z0-9_]{3,}", _normalize_text(text))
        if len(t) >= 4 and t not in stopwords
    }


def _freshness_for_timestamp(ts: datetime) -> tuple[float, str, float]:
    now_utc = datetime.utcnow()
    event_ts = ts
    if event_ts.tzinfo is not None:
        event_ts = event_ts.astimezone(timezone.utc).replace(tzinfo=None)
    age_hours = max(0.0, (now_utc - event_ts).total_seconds() / 3600.0)
    if age_hours < 6:
        return 1.15, "<6h", 1.0
    if age_hours < 24:
        return 1.08, "<24h", 0.75
    if age_hours < 72:
        return 1.00, "<72h", 0.5
    return 0.90, ">72h", 0.25


def _topic_keywords() -> dict[str, tuple[str, ...]]:
    return {
        "crypto": ("crypto", "kripto", "btc", "bitcoin", "eth", "ethereum", "altcoin", "stablecoin", "usdt"),
        "market": ("market", "piyasa", "trading", "borsa", "fiyat", "price", "likidite", "liquidity"),
        "economy": ("economy", "ekonomi", "enflasyon", "faiz", "fed", "rate", "cpi", "macro", "makro"),
        "security": ("security", "guvenlik", "breach", "hack", "saldiri", "ihlal", "sizinti", "ransomware", "cyber"),
        "global": ("global", "jeopolitik", "geopolitic", "savas", "war", "sanction", "ticaret", "trade"),
        "company": ("company", "sirket", "earnings", "bilanco", "ceo", "kurumsal", "corporate"),
        "tech": ("tech", "teknoloji", "ai", "outage", "cloud", "infrastructure", "altyapi", "chip", "semiconductor"),
    }


def extract_query_topics(query: str) -> dict:
    q_norm = _normalize_text(query)
    q_tokens = _tokenize(q_norm)
    topics: list[str] = []
    category_bias: list[str] = []
    topic_to_category = {
        "crypto": "economy",
        "market": "economy",
        "economy": "economy",
        "security": "security",
        "global": "global",
        "company": "other",
        "tech": "tech",
    }
    for topic, keywords in _topic_keywords().items():
        if any(k in q_norm for k in keywords):
            topics.append(topic)
            mapped = topic_to_category.get(topic)
            if mapped and mapped not in category_bias:
                category_bias.append(mapped)
    if not topics and any(k in q_norm for k in ("risk", "impact", "etki", "watch", "izle", "analiz")):
        topics.append("market")
        category_bias.append("economy")
    return {
        "topics": topics,
        "tokens": sorted(list(q_tokens))[:30],
        "category_bias": category_bias,
    }


def _event_topic_hits(event: IntelEvent, query_topics: list[str]) -> float:
    if not query_topics:
        return 0.0
    blob = " ".join(
        [
            str(event.title or ""),
            str(event.summary or ""),
            str(event.category or ""),
            " ".join([str(t) for t in (event.tags or [])]),
        ]
    )
    blob_norm = _normalize_text(blob)
    keys = _topic_keywords()
    hits = 0
    for topic in query_topics:
        kws = keys.get(topic, ())
        if any(k in blob_norm for k in kws):
            hits += 1
    return min(1.0, hits / max(1, len(query_topics)))


def _is_noise_event(event: IntelEvent) -> bool:
    source_norm = _normalize_text(str(event.source or ""))
    if source_norm in {"test", "demo", "synthetic"}:
        return True
    blob = _normalize_text(
        " ".join(
            [
                str(event.title or ""),
                str(event.summary or ""),
                " ".join([str(t) for t in (event.tags or [])]),
                str(event.source or ""),
            ]
        )
    )
    markers = (
        " test event ",
        " event sample ",
        " sample payload ",
        " dummy ",
        " synthetic ",
        " auth fix ",
    )
    padded = f" {blob} "
    return any(m in padded for m in markers)


class IntelService:
    def __init__(self, store: IntelStore, openai_client=None, profile_loader: Callable[[], dict] | None = None):
        self.store = store
        self.openai_client = openai_client
        self.profile_loader = profile_loader

    def get_latest_events(self, limit: int = 10) -> list[IntelEvent]:
        return self.store.get_latest_events(limit=limit)

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
        source_reliability = self._source_reliability(event.source)
        summary_quality = min(1.0, max(0.0, len((event.summary or "").strip()) / 260.0))
        tags_quality = min(1.0, len(event.tags or []) / 4.0)
        confidence_score = max(0.2, min(0.98, (source_reliability * 0.7) + (summary_quality * 0.2) + (tags_quality * 0.1)))
        source_multiplier = self._source_multiplier(event.source)
        raw_final = (importance_score * 0.45) + (urgency_score * 0.25) + (confidence_score * 0.30)
        final_score = max(0.05, min(1.0, raw_final * source_multiplier))
        return {
            "importance_score": round(importance_score, 4),
            "urgency_score": round(urgency_score, 4),
            "confidence_score": round(confidence_score, 4),
            "final_score": round(final_score, 4),
        }

    def _source_reliability(self, source: str) -> float:
        src = _normalize_text(source).strip()
        trust_map = {
            "official": 0.95,
            "official_feed": 0.93,
            "trusted_feed": 0.90,
            "manual": 0.88,
            "n8n": 0.82,
            "seed": 0.78,
            "tool_router": 0.75,
            "unknown": 0.45,
            "": 0.45,
        }
        if src in trust_map:
            return trust_map[src]
        if any(k in src for k in ("official", "gov", "exchange", "regulator")):
            return 0.9
        if any(k in src for k in ("seed", "demo", "test")):
            return 0.72
        if any(k in src for k in ("unknown", "anon", "unverified")):
            return 0.4
        return 0.65

    def _source_multiplier(self, source: str) -> float:
        src = _normalize_text(source).strip()
        mult_map = {
            "official": 1.08,
            "official_feed": 1.06,
            "trusted_feed": 1.04,
            "manual": 1.02,
            "n8n": 1.0,
            "seed": 0.96,
            "tool_router": 0.95,
            "unknown": 0.88,
            "": 0.88,
        }
        if src in mult_map:
            return mult_map[src]
        if any(k in src for k in ("official", "gov", "exchange", "regulator")):
            return 1.05
        if any(k in src for k in ("unknown", "anon", "unverified")):
            return 0.88
        return 0.97

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

    def filter_by_user_profile(
        self,
        events: list[IntelEvent],
        user_id: str,
        *,
        limit: int = 10,
        profile: dict | None = None,
    ) -> list[IntelEvent]:
        """
        Profile-aware relevance scoring:
        - category match: +0.3
        - matching tags: +0.2 each (max +0.4)
        - topic keyword match in title+summary: +0.3
        - freshness (<6h): +0.1
        - drop events with relevance <0.2
        Final rank = (original_importance_score * 0.6) + (relevance_score * 0.4)
        """
        _ = user_id
        rows = list(events or [])
        if not rows:
            return []
        safe_limit = max(1, min(100, int(limit or 10)))

        def _as_keyword_set(value) -> set[str]:
            out: set[str] = set()
            if isinstance(value, str):
                norm = _normalize_text(value).strip()
                if norm:
                    out.add(norm)
                out |= _tokenize(norm)
                return out
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    out |= _as_keyword_set(item)
                return out
            return out

        profile_data: dict = {}
        if isinstance(profile, dict):
            profile_data = profile
        elif callable(self.profile_loader):
            try:
                loaded = self.profile_loader()
                if isinstance(loaded, dict):
                    profile_data = loaded
            except Exception as exc:
                logger.info("PROFILE_LOAD_FAIL reason=%s", exc)
                profile_data = {}

        preferred_categories = _as_keyword_set(profile_data.get("preferred_categories") or profile_data.get("categories") or [])
        interests = _as_keyword_set(profile_data.get("interests") or profile_data.get("preferences") or [])
        topics = _as_keyword_set(profile_data.get("topics") or profile_data.get("focus_projects") or [])

        has_profile_preferences = bool(preferred_categories or interests or topics)

        def _original_importance_score(event: IntelEvent) -> float:
            raw = float(getattr(event, "importance_score", 0.0) or 0.0)
            if raw <= 0.0:
                raw = max(0.0, min(1.0, float(getattr(event, "importance", 0) or 0.0) / 10.0))
            return max(0.0, min(1.0, raw))

        if not has_profile_preferences:
            ordered = sorted(rows, key=_original_importance_score, reverse=True)
            return ordered[:safe_limit]

        now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
        ranked: list[tuple[float, float, float, IntelEvent]] = []
        for event in rows:
            relevance = 0.0
            category_norm = _normalize_text(str(getattr(event, "category", "") or "")).strip()
            if category_norm and category_norm in preferred_categories:
                relevance += 0.3

            tags = list(getattr(event, "tags", []) or [])
            tag_match_count = 0
            for tag in tags:
                tag_norm = _normalize_text(str(tag or "")).strip()
                if tag_norm and tag_norm in interests:
                    tag_match_count += 1
            relevance += min(0.4, float(tag_match_count) * 0.2)

            blob = _normalize_text(
                f"{str(getattr(event, 'title', '') or '')} {str(getattr(event, 'summary', '') or '')}"
            )
            if topics and any(topic in blob for topic in topics):
                relevance += 0.3

            ts = getattr(event, "timestamp", None)
            if isinstance(ts, datetime):
                event_utc = ts.astimezone(timezone.utc) if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
                age_hours = (now_utc - event_utc).total_seconds() / 3600.0
                if 0.0 <= age_hours < 6.0:
                    relevance += 0.1

            relevance = max(0.0, min(1.0, relevance))
            if relevance < 0.2:
                continue

            original_score = _original_importance_score(event)
            final_rank = (original_score * 0.6) + (relevance * 0.4)
            ranked.append((final_rank, original_score, relevance, event))

        ranked.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        return [item[3] for item in ranked[:safe_limit]]

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
        user_filtered = self.filter_by_user_profile(events, user_id=user_id, limit=10)
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

    ranked_events: list[tuple[float, float, str, IntelEvent]] = []
    for event in filtered:
        freshness_multiplier, time_window, _ = _freshness_for_timestamp(event.timestamp)
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


def select_relevant_intel_context(
    service: IntelService,
    query: str,
    user_id: str,
    max_events: int = 5,
) -> dict:
    query_info = extract_query_topics(query)
    query_tokens = set(query_info.get("tokens") or [])
    query_topics = list(query_info.get("topics") or [])
    query_categories = set(query_info.get("category_bias") or [])

    events = service.store.get_all_events()
    filtered = service.filter_by_user_profile(events, user_id=user_id)
    timeframe_selection = select_intel_by_timeframe(filtered, query)
    comparison_block = ""
    timeframe_mode = "none"
    if isinstance(timeframe_selection, dict):
        timeframe_mode = str(timeframe_selection.get("mode") or "single")
        if timeframe_mode == "compare":
            old_events = list(timeframe_selection.get("old_events") or [])
            new_events = list(timeframe_selection.get("new_events") or [])
            comparison_block = build_comparison_block(old_events, new_events)
            filtered = old_events + new_events
            logger.info("INTEL_TIMEFRAME mode=compare old=%s new=%s", len(old_events), len(new_events))
        else:
            scoped = list(timeframe_selection.get("events") or [])
            filtered = scoped
            logger.info("INTEL_TIMEFRAME mode=single count=%s", len(scoped))
    timeframe_active = timeframe_mode != "none"
    ranked: list[tuple[float, float, float, float, str, IntelEvent]] = []

    for event in filtered:
        if _is_noise_event(event):
            continue
        title_tokens = _tokenize(event.title)
        summary_tokens = _tokenize(event.summary)
        tag_tokens = _tokenize(" ".join([str(t) for t in (event.tags or [])]))
        category_tokens = _tokenize(event.category) or {_normalize_text(event.category)}

        title_overlap = len(query_tokens & title_tokens)
        summary_overlap = len(query_tokens & summary_tokens)
        tag_overlap = len(query_tokens & tag_tokens)
        category_overlap = len(query_tokens & category_tokens)

        overlap_raw = (title_overlap * 2.0) + (tag_overlap * 1.8) + (category_overlap * 1.4) + (summary_overlap * 1.0)
        overlap_norm = min(1.0, overlap_raw / max(2.0, float(len(query_tokens) * 1.7)))

        topic_hit = _event_topic_hits(event, query_topics)
        category_bias_boost = 0.15 if query_categories and _normalize_text(event.category) in query_categories else 0.0
        query_match_score = min(1.0, (overlap_norm * 0.72) + (topic_hit * 0.28) + category_bias_boost)

        event_cat = _normalize_text(event.category)
        if not timeframe_active:
            if query_categories and event_cat not in query_categories and topic_hit <= 0.0 and overlap_raw <= 0.0:
                continue
            if query_tokens and query_match_score < 0.08:
                continue

        freshness_multiplier, time_window, freshness_bonus = _freshness_for_timestamp(event.timestamp)
        effective_relevance_score = (query_match_score * 0.60) + (float(event.final_score) * 0.25) + (freshness_bonus * 0.15)
        ranked.append(
            (
                float(effective_relevance_score),
                float(query_match_score),
                float(freshness_multiplier),
                float(freshness_bonus),
                time_window,
                event,
            )
        )

    ranked.sort(key=lambda x: x[0], reverse=True)

    seen_titles: set[str] = set()
    key_events: list[dict] = []
    time_windows: list[str] = []
    for effective_score, query_score, freshness_multiplier, _, time_window, event in ranked:
        normalized = re.sub(r"\s+", " ", _normalize_text(event.title))
        if not normalized or normalized in seen_titles:
            continue
        if query_score < 0.12 and key_events:
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
                "query_match_score": round(float(query_score), 4),
                "freshness_multiplier": round(float(freshness_multiplier), 2),
                "importance": int(event.importance),
                "source": event.source,
                "tags": list(event.tags or [])[:4],
                "timestamp": event.timestamp.isoformat(),
            }
        )
        if len(key_events) >= max(1, min(5, max_events)):
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

    if comparison_block:
        summary = comparison_block
    elif key_events:
        topics_text = ", ".join(query_topics) if query_topics else "general"
        summary = " | ".join(
            [f"{item['title']} (q:{item['query_match_score']:.2f}, score:{item['effective_score']:.2f})" for item in key_events[:3]]
        )
        summary = f"Query topics={topics_text}. {summary}"
    else:
        summary = "No relevant events matched the current query focus."

    dominant_time_window = max(set(time_windows), key=time_windows.count) if time_windows else "unknown"
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
        "query_focus": query_info,
        "timeframe_mode": timeframe_mode,
    }


def select_intel_by_timeframe(events: list[IntelEvent], query_text: str) -> dict | None:
    q = _normalize_text(query_text)

    has_today = any(token in q for token in ("bugun", "today"))
    has_yesterday = any(token in q for token in ("dun", "yesterday"))
    has_this_week = any(token in q for token in ("bu hafta", "this week"))
    has_last_week = any(token in q for token in ("gecen hafta", "last week"))
    has_compare = any(token in q for token in ("karsilastir", "compare", "versus", "vs"))

    if not any((has_today, has_yesterday, has_this_week, has_last_week, has_compare)):
        return None

    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)

    def _events_in_age_window(min_hours: float, max_hours: float) -> list[IntelEvent]:
        rows: list[tuple[datetime, IntelEvent]] = []
        for event in list(events or []):
            ts = getattr(event, "timestamp", None)
            if not isinstance(ts, datetime):
                continue
            event_utc = ts.astimezone(timezone.utc) if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
            age_hours = (now_utc - event_utc).total_seconds() / 3600.0
            if min_hours <= age_hours < max_hours:
                rows.append((event_utc, event))
        rows.sort(key=lambda x: x[0], reverse=True)
        return [row[1] for row in rows]

    if has_compare:
        if has_this_week or has_last_week:
            old_events = _events_in_age_window(24.0 * 7.0, 24.0 * 14.0)
            new_events = _events_in_age_window(0.0, 24.0 * 7.0)
        else:
            old_events = _events_in_age_window(24.0, 48.0)
            new_events = _events_in_age_window(0.0, 24.0)
        return {
            "mode": "compare",
            "old_events": old_events,
            "new_events": new_events,
        }

    if has_yesterday:
        return {
            "mode": "single",
            "events": _events_in_age_window(24.0, 48.0),
            "label": "yesterday",
        }
    if has_today:
        return {
            "mode": "single",
            "events": _events_in_age_window(0.0, 24.0),
            "label": "today",
        }
    if has_last_week:
        return {
            "mode": "single",
            "events": _events_in_age_window(24.0 * 7.0, 24.0 * 14.0),
            "label": "last_week",
        }
    return {
        "mode": "single",
        "events": _events_in_age_window(0.0, 24.0 * 7.0),
        "label": "this_week",
    }


def build_comparison_block(old_events: list[IntelEvent], new_events: list[IntelEvent]) -> str:
    def _period_date(events: list[IntelEvent]) -> str:
        dated: list[datetime] = []
        for event in events:
            ts = getattr(event, "timestamp", None)
            if not isinstance(ts, datetime):
                continue
            event_utc = ts.astimezone(timezone.utc) if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
            dated.append(event_utc)
        if not dated:
            return "veri yok"
        return max(dated).date().isoformat()

    def _event_lines(events: list[IntelEvent]) -> list[str]:
        out: list[str] = []
        for event in events[:3]:
            title = str(getattr(event, "title", "") or "").strip() or "Baslik yok"
            summary = str(getattr(event, "summary", "") or "").strip()[:160] or "Ozet yok"
            out.append(f"- {title}: {summary}")
        if not out:
            out.append("- Bu donemde olay verisi yok.")
        return out

    old_titles = {
        _normalize_text(str(getattr(event, "title", "") or "").strip())
        for event in old_events
        if str(getattr(event, "title", "") or "").strip()
    }
    new_titles = {
        _normalize_text(str(getattr(event, "title", "") or "").strip())
        for event in new_events
        if str(getattr(event, "title", "") or "").strip()
    }
    added = sorted(list(new_titles - old_titles))
    removed = sorted(list(old_titles - new_titles))
    stable = sorted(list(new_titles & old_titles))

    if added:
        diff = f"Yeni donemde artan basliklar: {', '.join(added[:3])}."
    elif removed:
        diff = f"Onceki doneme gore zayiflayan basliklar: {', '.join(removed[:3])}."
    elif stable:
        diff = f"Benzer hat devam ediyor: {', '.join(stable[:3])}."
    else:
        diff = "Karsilastirma icin yeterli olay yok."

    old_date = _period_date(old_events)
    new_date = _period_date(new_events)
    return (
        "ZAMAN KARŞILAŞTIRMASI:\n\n"
        f"[Önceki Dönem - {old_date}]\n"
        + "\n".join(_event_lines(old_events))
        + "\n\n"
        f"[Güncel Dönem - {new_date}]\n"
        + "\n".join(_event_lines(new_events))
        + "\n\n"
        f"Fark: {diff}"
    )


def summarize_intel_context(intel_context: dict, *, max_chars: int = 1000) -> str:
    key_events = intel_context.get("key_events") or []
    compact = {
        "summary": str(intel_context.get("summary") or "").strip(),
        "signals": intel_context.get("signals") or [],
        "confidence": float(intel_context.get("confidence") or 0.0),
        "recency_note": str(intel_context.get("recency_note") or "").strip(),
        "events": [
            {
                "title": str(item.get("title") or "").strip(),
                "category": str(item.get("category") or "").strip(),
                "score": float(item.get("effective_score") or item.get("score") or 0.0),
            }
            for item in key_events[:5]
        ],
    }
    text = json.dumps(compact, ensure_ascii=False)
    if len(text) > max_chars:
        text = text[:max_chars]
    return text
