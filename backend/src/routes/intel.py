from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices

router = APIRouter()


@router.get("/intel")
def intel_brief(services: BackendServices = Depends(get_services)) -> dict:
    return services.intel.get_daily_brief()
