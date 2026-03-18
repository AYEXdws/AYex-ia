"""Compatibility wrapper.

Legacy imports (`ayex_api.server:app`) still work, while the implementation now
lives in `backend/src` with modular routes/services.
"""

from backend.src.index import app
from backend.src.schemas import (
    ActionRequest,
    ActionResponse,
    ChatRequest,
    ChatResponse,
    EventRequest,
    EventResponse,
    TTSRequest,
)

__all__ = [
    "app",
    "ChatRequest",
    "ChatResponse",
    "ActionRequest",
    "ActionResponse",
    "TTSRequest",
    "EventRequest",
    "EventResponse",
]
