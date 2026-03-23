from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Callable

from backend.src.intel.event_model import IntelEvent
from backend.src.intel.intel_store import IntelStore
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)
_ALLOWED_CATEGORIES = {"economy", "security", "tech", "global", "other"}
_CATEGORY_ALIAS = {
    "economy": "economy",
    "market": "economy",
    "finance": "economy",
    "financial": "economy",
    "crypto": "economy",
    "macroeconomy": "economy",
    "macro": "economy",
    "security": "security",
    "cyber": "security",
    "cybersecurity": "security",
    "infosec": "security",
    "tech": "tech",
    "technology": "tech",
    "ai": "tech",
    "global": "global",
    "world": "global",
    "geopolitics": "global",
    "geopolitic": "global",
    "other": "other",
}
_SOURCE_CATEGORY_HINTS = {
    "bbc_world": "global",
    "reuters": "global",
    "the_hacker_news": "security",
    "coingecko": "economy",
    "yahoo_finance": "economy",
    "er_api": "economy",
}
_GENERIC_TAGS = {"dunya", "haber", "gundem", "news", "world", "update", "breaking"}
_LOW_SIGNAL_WORLD_MARKERS = (
    "k-pop",
    "bts",
    "fans gather",
    "comeback show",
    "comeback",
    "onlyfans",
    "pornographic content",
    "celebrity",
    "showbiz",
    "entertainment",
    "influencer",
)


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_event_timestamp(value) -> datetime:
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    if value is None:
        return now_utc.replace(tzinfo=None)
    dt: datetime
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        epoch = float(value)
        if epoch > 10_000_000_000:
            epoch = epoch / 1000.0
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return now_utc.replace(tzinfo=None)
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp_invalid") from exc
    else:
        raise ValueError("timestamp_invalid")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    if dt > (now_utc + timedelta(minutes=15)):
        raise ValueError("timestamp_future")
    if dt < (now_utc - timedelta(days=90)):
        raise ValueError("timestamp_too_old")

    return dt.replace(tzinfo=None)


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


def _contains_keyword(blob: str, keyword: str) -> bool:
    normalized_keyword = _normalize_text(keyword).strip()
    if not normalized_keyword:
        return False
    if re.search(r"[a-z0-9]", normalized_keyword) is None:
        return normalized_keyword in blob
    if " " in normalized_keyword or "-" in normalized_keyword or "/" in normalized_keyword:
        return normalized_keyword in blob
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
    return re.search(pattern, blob) is not None


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


def _category_keywords() -> dict[str, tuple[str, ...]]:
    topics = _topic_keywords()
    return {
        "economy": topics["economy"] + topics["market"] + topics["crypto"],
        "security": topics["security"] + ("cve", "exploit", "malware", "rce", "vulnerability", "oracle", "patches"),
        "tech": topics["tech"] + ("platform", "device", "software", "app", "model", "bedrock"),
        "global": topics["global"] + ("missile", "israel", "iran", "hezbollah", "election", "minister", "border", "blackout", "power grid", "workers", "india"),
    }


def _infer_event_category(*, source: str, title: str, summary: str, category: str) -> str:
    blob = _normalize_text(" ".join([title, summary]))
    scores: dict[str, float] = {key: 0.0 for key in _ALLOWED_CATEGORIES}
    if category in scores:
        scores[category] += 0.35
    source_hint = _SOURCE_CATEGORY_HINTS.get(source)
    if source_hint in scores:
        scores[source_hint] += 0.45
    for candidate, keywords in _category_keywords().items():
        for keyword in keywords:
            if _contains_keyword(blob, keyword):
                scores[candidate] += 0.18
    best = max(scores.items(), key=lambda item: item[1])[0]
    return best if scores[best] > 0 else category


def _derive_tags(*, source: str, title: str, summary: str, category: str, tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        if not tag or tag in _GENERIC_TAGS:
            continue
        if tag not in cleaned:
            cleaned.append(tag)

    blob = _normalize_text(" ".join([title, summary]))
    keyword_tags = {
        "btc": ("btc", "bitcoin"),
        "eth": ("eth", "ethereum"),
        "rce": ("rce", "remote code execution"),
        "cve": ("cve-", "cve "),
        "war": ("war", "ground invasion", "savas"),
        "missile": ("missile", "ballistic"),
        "election": ("election", "vote", "poll"),
        "energy": ("blackout", "power grid", "electricity"),
        "trade": ("trade", "tariff", "sanction"),
        "ai": ("ai", "model", "bedrock"),
        "makro": ("usd/try", "eur/usd", "gbp/usd", "forex", "makro"),
    }
    for tag, markers in keyword_tags.items():
        if any(_contains_keyword(blob, marker) for marker in markers) and tag not in cleaned:
            cleaned.append(tag)

    if source in {"bbc_world", "reuters"} and category == "global":
        for country_tag, markers in {
            "israel": ("israel",),
            "iran": ("iran",),
            "lebanon": ("lebanon", "hezbollah"),
            "france": ("france", "paris", "marseille"),
            "germany": ("germany",),
            "india": ("india",),
            "cuba": ("cuba",),
        }.items():
            if any(_contains_keyword(blob, marker) for marker in markers) and country_tag not in cleaned:
                cleaned.append(country_tag)

    if not cleaned and category:
        cleaned.append(category)
    return cleaned[:5]


def _is_low_signal_world_event(*, source: str, title: str, summary: str, importance: int, category: str) -> bool:
    if source not in {"bbc_world", "reuters"}:
        return False
    if importance >= 8:
        return False
    if category in {"security", "economy"}:
        return False
    blob = _normalize_text(" ".join([title, summary]))
    if any(marker in blob for marker in _LOW_SIGNAL_WORLD_MARKERS):
        return True
    return False


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


def is_general_news_query(text: str) -> bool:
    general_keywords = [
        "neler oldu",
        "dunya",
        "haberler",
        "gundem",
        "bugun ne",
        "son dakika",
        "gelismeler",
        "ne var ne yok",
        "ozet",
        "brief",
        "rapor",
    ]
    q = _normalize_text(text)
    return any(kw in q for kw in general_keywords)


def _event_to_utc(ts) -> datetime:
    if not isinstance(ts, datetime):
        return datetime.min.replace(tzinfo=timezone.utc)
    if ts.tzinfo is not None:
        return ts.astimezone(timezone.utc)
    return ts.replace(tzinfo=timezone.utc)


def _format_short_date(dt_value: datetime) -> str:
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    idx = max(1, min(12, int(dt_value.month))) - 1
    return f"{int(dt_value.day):02d} {months[idx]}"


def _load_archive_events(service: "IntelService", *, lookback_days: int = 21) -> list[IntelEvent]:
    archive = getattr(service.store, "archive", None)
    if archive is None:
        return []
    end_day = datetime.utcnow().date()
    start_day = end_day - timedelta(days=max(2, int(lookback_days)))
    try:
        rows = list(archive.get_events_by_range(start_day.isoformat(), end_day.isoformat()) or [])
        return rows
    except Exception as exc:
        logger.info("INTEL_ARCHIVE_RANGE_READ_FAIL start=%s end=%s error=%s", start_day.isoformat(), end_day.isoformat(), exc)
        return []


def _events_in_age_window(events: list[IntelEvent], *, min_hours: float, max_hours: float) -> list[IntelEvent]:
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    rows: list[tuple[datetime, IntelEvent]] = []
    for event in list(events or []):
        if _is_noise_event(event):
            continue
        event_utc = _event_to_utc(getattr(event, "timestamp", None))
        if event_utc == datetime.min.replace(tzinfo=timezone.utc):
            continue
        age_hours = (now_utc - event_utc).total_seconds() / 3600.0
        if min_hours <= age_hours < max_hours:
            rows.append((event_utc, event))
    rows.sort(key=lambda x: x[0], reverse=True)
    return [row[1] for row in rows]


def _pick_general_latest_events(events: list[IntelEvent], *, max_events: int) -> list[IntelEvent]:
    safe_limit = max(1, min(10, int(max_events or 5)))
    ordered = sorted(
        list(events or []),
        key=lambda ev: _event_to_utc(getattr(ev, "timestamp", None)),
        reverse=True,
    )
    selected: list[IntelEvent] = []
    seen_titles: set[str] = set()

    def _try_add(event: IntelEvent) -> bool:
        if _is_noise_event(event):
            return False
        title_key = re.sub(r"\s+", " ", _normalize_text(str(getattr(event, "title", "") or "").strip()))
        if not title_key or title_key in seen_titles:
            return False
        seen_titles.add(title_key)
        selected.append(event)
        return True

    required_categories = ("economy", "security", "global", "tech")
    for required in required_categories:
        for event in ordered:
            category_norm = _normalize_text(str(getattr(event, "category", "") or "")).strip()
            if category_norm != required:
                continue
            if _try_add(event):
                break
        if len(selected) >= safe_limit:
            return sorted(
                selected[:safe_limit],
                key=lambda ev: _event_to_utc(getattr(ev, "timestamp", None)),
                reverse=True,
            )

    for event in ordered:
        if len(selected) >= safe_limit:
            break
        _try_add(event)
    return sorted(
        selected[:safe_limit],
        key=lambda ev: _event_to_utc(getattr(ev, "timestamp", None)),
        reverse=True,
    )


def _event_identity(event: IntelEvent) -> str:
    event_id = str(getattr(event, "id", "") or "").strip()
    title_key = re.sub(r"\s+", " ", _normalize_text(str(getattr(event, "title", "") or "").strip()))
    ts_key = _event_to_utc(getattr(event, "timestamp", None)).isoformat()
    return f"{event_id}|{title_key}|{ts_key}"


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
    def __init__(
        self,
        store: IntelStore,
        openai_client=None,
        profile_loader: Callable[[], dict] | None = None,
        fast_model: str = "gpt-4o",
    ):
        self.store = store
        self.openai_client = openai_client
        self.profile_loader = profile_loader
        self.fast_model = (fast_model or "gpt-4o").strip()

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
        title = _clean_text(payload.get("title") or "")
        summary = _clean_text(payload.get("summary") or "")
        if len(title) < 8 or len(title) > 220:
            raise ValueError("title_invalid")
        if len(summary) < 16 or len(summary) > 1600:
            raise ValueError("summary_invalid")

        category_raw = _normalize_text(_clean_text(payload.get("category") or "other"))
        category = _CATEGORY_ALIAS.get(category_raw, category_raw)
        if category not in _ALLOWED_CATEGORIES:
            raise ValueError("category_invalid")

        importance_raw = payload.get("importance", 5)
        try:
            importance = int(float(importance_raw))
        except (TypeError, ValueError):
            raise ValueError("importance_invalid")
        importance = max(1, min(10, importance))

        tags_raw = payload.get("tags")
        tags: list[str] = []
        if isinstance(tags_raw, list):
            for item in tags_raw:
                val = _normalize_text(_clean_text(item))
                if not val:
                    continue
                val = re.sub(r"[^a-z0-9_\-.:]+", "", val)
                if not val:
                    continue
                tags.append(val[:32])
                if len(tags) >= 5:
                    break

        source = _normalize_text(_clean_text(payload.get("source") or "n8n"))
        source = re.sub(r"[^a-z0-9_\-.:]+", "_", source).strip("_")
        if len(source) < 2 or len(source) > 64:
            raise ValueError("source_invalid")

        category = _infer_event_category(source=source, title=title, summary=summary, category=category)
        tags = _derive_tags(source=source, title=title, summary=summary, category=category, tags=tags)
        if _is_low_signal_world_event(source=source, title=title, summary=summary, importance=importance, category=category):
            raise ValueError("low_signal_event")

        ts = _normalize_event_timestamp(payload.get("timestamp"))

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
        logger.info("MODEL_SELECTED model=%s mode=%s reason=%s", self.fast_model, "intel_analysis", "event_analysis")
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
                model=self.fast_model,
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
        logger.info("MODEL_SELECTED model=%s mode=%s reason=%s", self.fast_model, "intel_brief", "daily_brief_summary")
        prompt = (
            "Summarize the most important global events into a short intelligence brief.\n\n"
            f"Insights: {json.dumps(insights[:3], ensure_ascii=False)}"
        )
        try:
            res = self.openai_client.call_responses(
                prompt=prompt,
                model=self.fast_model,
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

    def get_historical_comparison(self, query_text: str, category: str = None) -> str:
        archive = getattr(self.store, "archive", None)
        if archive is None:
            return ""

        q = _normalize_text(query_text)
        wants_today = any(token in q for token in ("bugun", "today"))
        wants_yesterday = any(token in q for token in ("dun", "yesterday"))
        wants_compare = any(token in q for token in ("karsilastir", "compare", "versus", "vs"))
        if not any((wants_today, wants_yesterday, wants_compare)):
            return ""

        today_events = list(archive.get_today_events() or [])
        yesterday_events = list(archive.get_yesterday_events() or [])

        category_norm = _normalize_text(str(category or "")).strip()
        if category_norm:
            today_events = [e for e in today_events if _normalize_text(str(e.category or "")).strip() == category_norm]
            yesterday_events = [e for e in yesterday_events if _normalize_text(str(e.category or "")).strip() == category_norm]

        if wants_compare or (wants_today and wants_yesterday):
            return build_comparison_block(yesterday_events, today_events)

        target = today_events if wants_today else yesterday_events
        label = "BUGÜN" if wants_today else "DÜN"
        if not target:
            return f"{label} ARŞİVİ:\n- Uygun olay bulunamadı."

        lines: list[str] = []
        for event in target[:4]:
            ts = getattr(event, "timestamp", datetime.utcnow())
            ts_utc = ts.astimezone(timezone.utc) if getattr(ts, "tzinfo", None) is not None else ts
            ts_text = ts_utc.strftime("%Y-%m-%d %H:%M")
            lines.append(f"- [{ts_text}] {event.title}: {str(event.summary or '')[:160]}")
        return f"{label} ARŞİVİ:\n" + "\n".join(lines)

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


def get_all_intel_for_llm(
    service: "IntelService",
    query: str,
    user_id: str,
    max_events: int = 15,
) -> dict:
    """Tüm güncel event'leri LLM'e verir. Filtreleme YAPMAZ.

    LLM kendi analiz eder, çıkarım yapar, karşılaştırır.
    Scoring/filtering LLM'in işi, kodun değil.
    """
    _ = user_id
    events = list(service.store.get_all_events() or [])
    if not events:
        try:
            events = list(_load_archive_events(service, lookback_days=2) or [])
        except Exception:
            events = []

    if not events:
        return {
            "key_events": [],
            "summary": "Henüz veri yok.",
            "event_count": 0,
            "categories": [],
            "timeframe_info": "",
            "timeframe_mode": "none",
            "recency_note": "no_events",
        }

    sorted_events = sorted(
        events,
        key=lambda e: _event_to_utc(getattr(e, "timestamp", None)),
        reverse=True,
    )
    selected = sorted_events[: max(1, min(60, int(max_events or 15)))]

    categories: dict[str, list[str]] = {}
    key_events: list[dict[str, object]] = []

    for ev in selected:
        title = str(getattr(ev, "title", "") or "").strip()
        if not title:
            continue
        summary = str(getattr(ev, "summary", "") or "").strip()
        category = str(getattr(ev, "category", "other") or "other").strip()
        source = str(getattr(ev, "source", "unknown") or "unknown").strip()
        timestamp = getattr(ev, "timestamp", None)
        tags = list(getattr(ev, "tags", []) or [])[:5]
        importance = int(getattr(ev, "importance", 0) or 0)

        key_events.append(
            {
                "title": title,
                "summary": summary[:300],
                "category": category,
                "source": source,
                "tags": tags,
                "importance": importance,
                "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else "",
            }
        )
        categories.setdefault(category or "other", []).append(title)

    timeframe_info = ""
    timeframe_mode = "none"
    recency_note = "latest_events"
    try:
        timeframe_selection = select_intel_by_timeframe(service, query, fallback_events=events)
        if isinstance(timeframe_selection, dict):
            timeframe_mode = str(timeframe_selection.get("mode") or "none")
            if timeframe_mode == "compare":
                old_label = str(timeframe_selection.get("old_label") or "")
                new_label = str(timeframe_selection.get("new_label") or "")
                old_events = list(timeframe_selection.get("old_events") or [])
                new_events = list(timeframe_selection.get("new_events") or [])
                timeframe_info = f"KARSILASTIRMA: {old_label} ({len(old_events)} event) vs {new_label} ({len(new_events)} event)"
                recency_note = f"{old_label} vs {new_label}".strip()

                existing_titles = {str(item.get("title") or "").strip() for item in key_events}
                for ev in old_events:
                    title = str(getattr(ev, "title", "") or "").strip()
                    if not title or title in existing_titles:
                        continue
                    summary = str(getattr(ev, "summary", "") or "").strip()
                    category = str(getattr(ev, "category", "other") or "other").strip()
                    timestamp = getattr(ev, "timestamp", None)
                    source = str(getattr(ev, "source", "unknown") or "unknown").strip()
                    tags = list(getattr(ev, "tags", []) or [])[:5]
                    importance = int(getattr(ev, "importance", 0) or 0)
                    key_events.append(
                        {
                            "title": title,
                            "summary": summary[:300],
                            "category": category,
                            "source": source,
                            "tags": tags,
                            "importance": importance,
                            "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else "",
                            "time_context": old_label,
                        }
                    )
                    existing_titles.add(title)
                    categories.setdefault(category or "other", []).append(title)
            elif timeframe_selection.get("label_text"):
                timeframe_info = str(timeframe_selection.get("label_text") or "")
                recency_note = timeframe_info
    except Exception:
        pass

    category_list = sorted([str(c or "").strip() for c in categories.keys() if str(c or "").strip()])
    category_summary = ", ".join([f"{cat} ({len(titles)})" for cat, titles in categories.items()])
    summary_text = f"Toplam {len(key_events)} event. Kategoriler: {category_summary}" if key_events else "Henüz veri yok."

    return {
        "key_events": key_events,
        "summary": summary_text[:1200],
        "event_count": len(key_events),
        "categories": category_list,
        "timeframe_info": timeframe_info,
        "timeframe_mode": timeframe_mode,
        "recency_note": recency_note,
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
    general_query = is_general_news_query(query)

    events = service.store.get_all_events()
    profile_filtered = service.filter_by_user_profile(events, user_id=user_id)
    timeframe_selection = select_intel_by_timeframe(service, query, fallback_events=events)
    comparison_block = ""
    timeframe_mode = "none"
    timeframe_label = ""
    scoped_events: list[IntelEvent] | None = None
    time_labels: dict[str, str] = {}
    if isinstance(timeframe_selection, dict):
        timeframe_mode = str(timeframe_selection.get("mode") or "single")
        if timeframe_mode == "compare":
            old_events = list(timeframe_selection.get("old_events") or [])
            new_events = list(timeframe_selection.get("new_events") or [])
            old_label = str(timeframe_selection.get("old_label") or "")
            new_label = str(timeframe_selection.get("new_label") or "")
            comparison_block = build_comparison_block(
                old_events,
                new_events,
                old_label=old_label,
                new_label=new_label,
            )
            scoped_events = old_events + new_events
            for event in old_events:
                time_labels[_event_identity(event)] = old_label
            for event in new_events:
                time_labels[_event_identity(event)] = new_label
            logger.info(
                "INTEL_TIMEFRAME mode=compare old=%s new=%s old_label=%s new_label=%s",
                len(old_events),
                len(new_events),
                old_label,
                new_label,
            )
        else:
            scoped = list(timeframe_selection.get("events") or [])
            timeframe_label = str(timeframe_selection.get("label_text") or "")
            scoped_events = scoped
            for event in scoped:
                time_labels[_event_identity(event)] = timeframe_label
            logger.info("INTEL_TIMEFRAME mode=single count=%s label=%s", len(scoped), timeframe_label)

    timeframe_active = bool(scoped_events is not None)
    candidate_events = list(scoped_events or (events if general_query else profile_filtered))

    if general_query:
        selected_general = _pick_general_latest_events(
            candidate_events,
            max_events=max(1, min(5, int(max_events or 5))),
        )
        key_events: list[dict] = []
        time_windows: list[str] = []
        for event in selected_general:
            freshness_multiplier, time_window, _ = _freshness_for_timestamp(event.timestamp)
            effective_score = float(event.final_score) * freshness_multiplier
            event_label = time_labels.get(_event_identity(event), timeframe_label)
            time_windows.append(time_window)
            key_events.append(
                {
                    "title": event.title,
                    "summary": str(event.summary or "")[:220],
                    "category": event.category,
                    "score": round(float(event.final_score), 4),
                    "effective_score": round(float(effective_score), 4),
                    "query_match_score": 1.0,
                    "freshness_multiplier": round(float(freshness_multiplier), 2),
                    "importance": int(event.importance),
                    "source": event.source,
                    "tags": list(event.tags or [])[:4],
                    "timestamp": event.timestamp.isoformat(),
                    "time_context": event_label,
                }
            )

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
            categories = sorted(
                {
                    str(item.get("category") or "").strip()
                    for item in key_events
                    if str(item.get("category") or "").strip()
                }
            )
            categories_text = ", ".join(categories) if categories else "genel"
            title_summary = " | ".join([f"{item['title']} ({item['category']})" for item in key_events[:3]])
            if timeframe_label:
                summary = f"{timeframe_label}\n{title_summary}"
            else:
                summary = f"Genel gundem ({categories_text}): {title_summary}"
        else:
            summary = f"{timeframe_label}\nBu zaman araliginda olay verisi yok." if timeframe_label else "Guncel olay verisi yok."

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
            "recency_note": timeframe_label or f"dominant_time_window={dominant_time_window}",
            "query_focus": query_info,
            "timeframe_mode": timeframe_mode,
        }

    ranked: list[tuple[float, float, float, float, str, IntelEvent]] = []

    for event in candidate_events:
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
        event_label = time_labels.get(_event_identity(event), timeframe_label)
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
                "time_context": event_label,
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
        if timeframe_label:
            summary = f"{timeframe_label}\n{summary}"
    else:
        if timeframe_label:
            summary = f"{timeframe_label}\nBu zaman araliginda ilgili olay bulunamadi."
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
        "recency_note": timeframe_label or f"dominant_time_window={dominant_time_window}",
        "query_focus": query_info,
        "timeframe_mode": timeframe_mode,
    }


def select_intel_by_timeframe(
    service: IntelService,
    query_text: str,
    *,
    fallback_events: list[IntelEvent] | None = None,
) -> dict | None:
    q = _normalize_text(query_text)

    has_today = any(token in q for token in ("bugun", "today"))
    has_yesterday = any(token in q for token in ("dun", "dunku", "yesterday"))
    has_this_week = any(token in q for token in ("bu hafta", "this week"))
    has_last_week = any(token in q for token in ("gecen hafta", "last week"))
    has_compare = any(token in q for token in ("karsilastir", "compare", "fark", "versus", "vs"))

    if not any((has_today, has_yesterday, has_this_week, has_last_week, has_compare)):
        return None

    archive_events = _load_archive_events(service, lookback_days=21)
    pool = list(archive_events or fallback_events or [])
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)

    today_label = f"[Bugün - {_format_short_date(now_utc)}]"
    yesterday_label = f"[Dün - {_format_short_date(now_utc - timedelta(days=1))}]"
    this_week_start = now_utc - timedelta(days=6)
    last_week_end = now_utc - timedelta(days=7)
    last_week_start = now_utc - timedelta(days=13)
    this_week_label = f"[Bu Hafta - {_format_short_date(this_week_start)}-{_format_short_date(now_utc)}]"
    last_week_label = f"[Gecen Hafta - {_format_short_date(last_week_start)}-{_format_short_date(last_week_end)}]"

    if has_compare:
        if has_this_week or has_last_week:
            old_events = _events_in_age_window(pool, min_hours=24.0 * 7.0, max_hours=24.0 * 14.0)
            new_events = _events_in_age_window(pool, min_hours=0.0, max_hours=24.0 * 7.0)
            old_label = last_week_label
            new_label = this_week_label
        else:
            old_events = _events_in_age_window(pool, min_hours=24.0, max_hours=48.0)
            new_events = _events_in_age_window(pool, min_hours=0.0, max_hours=24.0)
            old_label = yesterday_label
            new_label = today_label
        return {
            "mode": "compare",
            "old_events": old_events,
            "new_events": new_events,
            "old_label": old_label,
            "new_label": new_label,
            "source": "archive" if archive_events else "store",
        }

    if has_yesterday:
        return {
            "mode": "single",
            "events": _events_in_age_window(pool, min_hours=24.0, max_hours=48.0),
            "label": "yesterday",
            "label_text": yesterday_label,
            "source": "archive" if archive_events else "store",
        }
    if has_today:
        return {
            "mode": "single",
            "events": _events_in_age_window(pool, min_hours=0.0, max_hours=24.0),
            "label": "today",
            "label_text": today_label,
            "source": "archive" if archive_events else "store",
        }
    if has_last_week:
        return {
            "mode": "single",
            "events": _events_in_age_window(pool, min_hours=24.0 * 7.0, max_hours=24.0 * 14.0),
            "label": "last_week",
            "label_text": last_week_label,
            "source": "archive" if archive_events else "store",
        }
    return {
        "mode": "single",
        "events": _events_in_age_window(pool, min_hours=0.0, max_hours=24.0 * 7.0),
        "label": "this_week",
        "label_text": this_week_label,
        "source": "archive" if archive_events else "store",
    }


def build_comparison_block(
    old_events: list[IntelEvent],
    new_events: list[IntelEvent],
    *,
    old_label: str | None = None,
    new_label: str | None = None,
) -> str:
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

    if not old_label:
        old_label = f"[Önceki Dönem - {_period_date(old_events)}]"
    if not new_label:
        new_label = f"[Güncel Dönem - {_period_date(new_events)}]"

    return (
        "ZAMAN KARŞILAŞTIRMASI:\n\n"
        f"{old_label}\n"
        + "\n".join(_event_lines(old_events))
        + "\n\n"
        f"{new_label}\n"
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
