from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices

router = APIRouter()


@router.get('/usage')
def usage(services: BackendServices = Depends(get_services)) -> dict:
    return {'status': 'ok', 'today': services.cost_guard.usage_today()}
