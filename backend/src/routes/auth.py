from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.src.services.auth_service import AuthService

router = APIRouter()
auth_service = AuthService()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    user_id = auth_service.authenticate(payload.username, payload.password)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth_service.create_token(user_id)
    return LoginResponse(access_token=token, user_id=user_id)
