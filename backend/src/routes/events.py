from __future__ import annotations

import hmac
import threading
import time
from collections import deque

from fastapi import APIRouter, Depends, Query, Request

from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices
from backend.src.utils.logging import get_logger, log_event

router = APIRouter()
logger = get_logger(__name__)
_INGEST_LOCK = threading.Lock()
_INGEST_HITS: dict[str, deque[float]] = {}


@router.get("/events/latest")
def latest_events(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    services: BackendServices = Depends(get_services),
) -> dict:
    _ = str(getattr(request.state, "user_id", "default"))
    events = services.intel.get_latest_events(limit=limit)
    rows = []
    for ev in events:
        rows.append(
            {
                "id": ev.id,
                "title": ev.title,
                "summary": ev.summary,
                "category": ev.category,
                "importance": ev.importance,
                "timestamp": ev.timestamp.isoformat(),
                "source": ev.source,
                "tags": list(ev.tags or []),
                "final_score": float(ev.final_score),
                "confidence_score": float(ev.confidence_score),
            }
        )
    return {"events": rows, "count": len(rows)}


@router.post("/events/ingest")
async def ingest_event(request: Request, services: BackendServices = Depends(get_services)) -> dict:
    user_id = str(getattr(request.state, "user_id", "default"))
    request_id = str(getattr(request.state, "request_id", ""))
    expected_token = str(getattr(services.settings, "intel_ingest_token", "") or "").strip()
    if expected_token:
        provided = (request.headers.get("x-ayex-ingest-token") or request.headers.get("x-intel-token") or "").strip()
        if not provided or not hmac.compare_digest(provided, expected_token):
            logger.info("EVENT_REJECTED reason=ingest_token_invalid")
            log_event(logger, "events_ingest_rejected", request_id=request_id, reason="unauthorized", user_id=user_id)
            return {"status": "skipped", "reason": "unauthorized"}

    try:
        body = await request.json()
        if not isinstance(body, dict):
            logger.info("EVENT_REJECTED reason=invalid_json_type")
            log_event(logger, "events_ingest_rejected", request_id=request_id, reason="invalid_json_type", user_id=user_id)
            return {"status": "skipped", "reason": "invalid"}
    except Exception:
        logger.info("EVENT_REJECTED reason=invalid_json_parse")
        log_event(logger, "events_ingest_rejected", request_id=request_id, reason="invalid_json_parse", user_id=user_id)
        return {"status": "skipped", "reason": "invalid"}

    # Backward-compatible: allow legacy payload wrapper {type, payload:{...}}
    merged = dict(body)
    payload_inner = body.get("payload")
    if isinstance(payload_inner, dict):
        merged = {**payload_inner, "type": body.get("type", payload_inner.get("type")), "source": body.get("source", payload_inner.get("source"))}

    source_hint = str(merged.get("source") or body.get("source") or "unknown").strip().lower() or "unknown"
    limit_per_minute = max(0, int(getattr(services.settings, "intel_ingest_rate_per_minute", 120) or 120))
    if limit_per_minute > 0:
        client_host = "unknown"
        if getattr(request, "client", None) and getattr(request.client, "host", None):
            client_host = str(request.client.host)
        rate_key = f"{client_host}|{source_hint}"
        now = time.monotonic()
        with _INGEST_LOCK:
            bucket = _INGEST_HITS.setdefault(rate_key, deque())
            while bucket and (now - bucket[0]) > 60.0:
                bucket.popleft()
            if len(bucket) >= limit_per_minute:
                logger.info("EVENT_REJECTED reason=rate_limited key=%s rpm=%s", rate_key, limit_per_minute)
                log_event(logger, "events_ingest_rejected", request_id=request_id, reason="rate_limited", key=rate_key, rpm=limit_per_minute)
                return {"status": "skipped", "reason": "rate_limited"}
            bucket.append(now)

    logger.info("EVENT_RECEIVED source=%s type=%s", merged.get("source"), merged.get("type"))
    try:
        cleaned = services.intel.validate_event_payload(merged)
        logger.info(
            "EVENT_VALIDATED title=%s importance=%s category=%s",
            cleaned["title"],
            cleaned["importance"],
            cleaned["category"],
        )
    except Exception as exc:
        logger.info("EVENT_REJECTED reason=invalid error=%s", exc)
        log_event(logger, "events_ingest_rejected", request_id=request_id, reason="invalid_payload", error=exc)
        return {"status": "skipped", "reason": "invalid"}

    created = services.intel.create_event(
        title=cleaned["title"],
        summary=cleaned["summary"],
        category=cleaned["category"],
        importance=cleaned["importance"],
        source=cleaned["source"],
        tags=cleaned["tags"],
        timestamp=cleaned["timestamp"],
    )
    if created is None:
        logger.info("EVENT_REJECTED reason=duplicate title=%s", cleaned["title"])
        log_event(logger, "events_ingest_rejected", request_id=request_id, reason="duplicate", title=cleaned["title"])
        return {"status": "skipped", "reason": "duplicate"}

    services.long_memory.append_event(
        event_type=cleaned["type"],
        payload={
            "title": cleaned["title"],
            "summary": cleaned["summary"],
            "category": cleaned["category"],
            "importance": cleaned["importance"],
            "tags": cleaned["tags"],
            "source": cleaned["source"],
            "timestamp": cleaned["timestamp"].isoformat(),
        },
        source=cleaned["source"],
        user_id=user_id,
    )
    logger.info("EVENT_STORED id=%s title=%s score=%s", created.id, created.title, created.final_score)
    log_event(
        logger,
        "events_ingest_stored",
        request_id=request_id,
        id=created.id,
        title=created.title,
        category=cleaned["category"],
        source=cleaned["source"],
    )
    return {"status": "ok", "stored": True}
