from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.src.services.auth_service import AuthService


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.auth = AuthService()
        self.protected_prefixes = ("/chat", "/action", "/events")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        if not self._is_protected(path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization") or ""
        if not auth_header.lower().startswith("bearer "):
            return JSONResponse(status_code=401, content={"status": "error", "detail": "Unauthorized"})

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return JSONResponse(status_code=401, content={"status": "error", "detail": "Unauthorized"})
        try:
            verified = self.auth.verify_token(token)
            request.state.user_id = verified["user_id"]
        except Exception:
            return JSONResponse(status_code=401, content={"status": "error", "detail": "Unauthorized"})
        return await call_next(request)

    def _is_protected(self, path: str) -> bool:
        for prefix in self.protected_prefixes:
            if path == prefix or path.startswith(f"{prefix}/"):
                return True
        return False
