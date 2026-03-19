from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices

router = APIRouter()


@router.get("/intel")
def intel_brief(request: Request, services: BackendServices = Depends(get_services)) -> dict:
    user_id = str(getattr(request.state, "user_id", "default"))
    return services.intel.get_daily_brief(user_id=user_id)
