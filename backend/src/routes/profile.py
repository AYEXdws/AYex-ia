from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.src.routes.deps import get_services
from backend.src.schemas import ProfileResponse, ProfileUpdateRequest
from backend.src.services.container import BackendServices

router = APIRouter()


@router.get("/profile", response_model=ProfileResponse)
def get_profile(services: BackendServices = Depends(get_services)) -> ProfileResponse:
    return ProfileResponse(profile=services.profile.load())


@router.patch("/profile", response_model=ProfileResponse)
def update_profile(payload: ProfileUpdateRequest, services: BackendServices = Depends(get_services)) -> ProfileResponse:
    profile = services.profile.update(payload.updates)
    return ProfileResponse(profile=profile)
