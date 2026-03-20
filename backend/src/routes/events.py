from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices
from backend.src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


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
    try:
        body = await request.json()
        if not isinstance(body, dict):
            logger.info("EVENT_REJECTED reason=invalid_json_type")
            return {"status": "skipped", "reason": "invalid"}
    except Exception:
        logger.info("EVENT_REJECTED reason=invalid_json_parse")
        return {"status": "skipped", "reason": "invalid"}

    # Backward-compatible: allow legacy payload wrapper {type, payload:{...}}
    merged = dict(body)
    payload_inner = body.get("payload")
    if isinstance(payload_inner, dict):
        merged = {**payload_inner, "type": body.get("type", payload_inner.get("type")), "source": body.get("source", payload_inner.get("source"))}

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
    return {"status": "ok", "stored": True}
