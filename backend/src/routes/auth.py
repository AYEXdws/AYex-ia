from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.src.routes.deps import get_services
from backend.src.services.container import BackendServices

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, services: BackendServices = Depends(get_services)) -> LoginResponse:
    user_id = services.auth.authenticate(payload.username, payload.password)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = services.auth.create_token(user_id)
    return LoginResponse(access_token=token, user_id=user_id)
