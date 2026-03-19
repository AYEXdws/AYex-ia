from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


class AuthService:
    def __init__(self):
        self.jwt_secret = (os.environ.get("AYEX_JWT_SECRET") or "").strip() or "change-me-ayex-jwt-secret"
        self.jwt_alg = "HS256"
        self.jwt_exp_hours = max(1, int(os.environ.get("AYEX_JWT_EXP_HOURS", "12")))

    def authenticate(self, username: str, password: str) -> str | None:
        expected_user = (os.environ.get("AYEX_USER") or "").strip()
        expected_pass = (os.environ.get("AYEX_PASS") or "").strip()
        if not expected_user or not expected_pass:
            return None
        if username.strip() != expected_user or password != expected_pass:
            return None
        return expected_user

    def create_token(self, user_id: str) -> str:
        now = datetime.now(tz=timezone.utc)
        payload = {
            "sub": user_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=self.jwt_exp_hours)).timestamp()),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_alg)

    def verify_token(self, token: str) -> dict[str, Any]:
        payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_alg])
        user_id = str(payload.get("sub") or "").strip()
        if not user_id:
            raise ValueError("Token subject is missing")
        return {"user_id": user_id, "payload": payload}
