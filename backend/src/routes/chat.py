from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.src.routes.deps import get_services
from backend.src.schemas import ChatRequest, ChatResponse
from backend.src.services.container import BackendServices

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, services: BackendServices = Depends(get_services)) -> ChatResponse:
    result = services.openclaw.run_action(payload.text, workspace=payload.workspace, model=payload.model)
    if not result.ok:
        return ChatResponse(
            reply="OpenClaw baglanti hatasi.",
            metrics={"source": "openclaw", "ok": False},
        )
    return ChatResponse(
        reply=result.text,
        metrics={"source": "openclaw", "ok": True},
    )
