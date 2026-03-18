from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    text: str
    workspace: Optional[str] = None
    model: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
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


class ActionResponse(BaseModel):
    status: str
    source: str
    reply: str
    raw: Dict[str, Any] = Field(default_factory=dict)
