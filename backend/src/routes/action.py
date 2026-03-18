from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.src.routes.deps import get_services
from backend.src.schemas import ActionRequest, ActionResponse
from backend.src.services.container import BackendServices

router = APIRouter()


@router.post("/action", response_model=ActionResponse)
def action(payload: ActionRequest, services: BackendServices = Depends(get_services)) -> ActionResponse:
    result = services.openclaw.run_action(payload.text, workspace=payload.workspace, model=payload.model)
    source = "openclaw"
    reply = result.text if result.ok else "OpenClaw baglanti hatasi."
    return ActionResponse(
        status="ok",
        source=source,
        reply=reply,
        raw=result.raw,
    )
