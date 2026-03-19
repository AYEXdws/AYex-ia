from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.src.routes.deps import get_services
from backend.src.schemas import EventRequest, EventResponse
from backend.src.services.container import BackendServices

router = APIRouter()


@router.post("/events/ingest", response_model=EventResponse)
def ingest_event(payload: EventRequest, services: BackendServices = Depends(get_services)) -> EventResponse:
    services.long_memory.append_event(
        event_type=(payload.type or "generic"),
        payload=payload.payload or {},
        source="n8n",
    )
    return EventResponse(
        status="ok",
        accepted=True,
        event_type=payload.type or "generic",
        note="Event memory'e yazildi.",
    )
