from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    text: str
    workspace: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    model: Optional[str] = None


class EventRequest(BaseModel):
    type: str = "generic"
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventResponse(BaseModel):
    status: str
    accepted: bool
    event_type: str
    note: str


class ActionRequest(BaseModel):
    text: str
    workspace: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None
    use_profile: bool = True


class ActionResponse(BaseModel):
    status: str
    source: str
    reply: str
    session_id: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)
    raw: Dict[str, Any] = Field(default_factory=dict)


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None


class SessionInfo(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    last_preview: str = ""
    turn_count: int = 0


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo] = Field(default_factory=list)


class MessageInfo(BaseModel):
    id: str
    session_id: str
    ts: str
    role: str
    text: str
    source: str = "ai"
    latency_ms: Optional[int] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class SessionMessagesResponse(BaseModel):
    session: Optional[SessionInfo] = None
    messages: list[MessageInfo] = Field(default_factory=list)


class DecisionFeedbackRequest(BaseModel):
    outcome_status: str
    note: Optional[str] = None


class ProfileResponse(BaseModel):
    profile: Dict[str, Any] = Field(default_factory=dict)


class ProfileUpdateRequest(BaseModel):
    updates: Dict[str, Any] = Field(default_factory=dict)
