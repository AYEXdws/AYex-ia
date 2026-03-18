from __future__ import annotations

from fastapi import APIRouter

from backend.src.schemas import EventRequest, EventResponse

router = APIRouter()


@router.post("/event", response_model=EventResponse)
def ingest_event(payload: EventRequest) -> EventResponse:
    return EventResponse(
        status="ok",
        accepted=True,
        event_type=payload.type,
        note="Event endpoint hazir. Sensor ve cihaz routing sonraki fazda genisletilecek.",
    )
