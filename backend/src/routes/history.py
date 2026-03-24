from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.src.routes.deps import get_services
from backend.src.schemas import DecisionFeedbackRequest, MessageInfo, SessionCreateRequest, SessionInfo, SessionListResponse, SessionMessagesResponse
from backend.src.services.container import BackendServices

router = APIRouter()
_ALLOWED_DECISION_OUTCOMES = {"dogru", "yanlis", "beklemede", "gecersiz"}


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=30, ge=1, le=200),
    services: BackendServices = Depends(get_services),
) -> SessionListResponse:
    sessions = [SessionInfo(**item) for item in services.chat_store.list_sessions(limit=limit)]
    return SessionListResponse(sessions=sessions)


@router.post("/sessions", response_model=SessionInfo)
def create_session(
    payload: SessionCreateRequest,
    services: BackendServices = Depends(get_services),
) -> SessionInfo:
    session = services.chat_store.create_session(title=payload.title)
    return SessionInfo(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_preview=session.last_preview,
        turn_count=session.turn_count,
    )


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def session_messages(
    session_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    services: BackendServices = Depends(get_services),
) -> SessionMessagesResponse:
    session = services.chat_store.get_session(session_id)
    if not session:
        return SessionMessagesResponse(session=None, messages=[])
    messages = [MessageInfo(**m) for m in services.chat_store.messages(session_id, limit=limit)]
    return SessionMessagesResponse(session=SessionInfo(**session), messages=messages)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, services: BackendServices = Depends(get_services)) -> dict:
    deleted = services.chat_store.delete_session(session_id)
    return {"status": "ok", "deleted": deleted}


@router.post("/sessions/{session_id}/messages/{message_id}/decision-feedback")
def decision_feedback(
    session_id: str,
    message_id: str,
    payload: DecisionFeedbackRequest,
    services: BackendServices = Depends(get_services),
) -> dict:
    outcome = str(payload.outcome_status or "").strip().lower()
    if outcome not in _ALLOWED_DECISION_OUTCOMES:
        return {"status": "invalid", "updated": False}
    patch = {
        "decision_feedback": {
            "outcome_status": outcome,
            "note": str(payload.note or "").strip(),
        }
    }
    updated = services.chat_store.update_message_metrics(session_id, message_id, patch)
    return {"status": "ok", "updated": bool(updated), "message_id": message_id, "outcome_status": outcome}
