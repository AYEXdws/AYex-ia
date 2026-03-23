from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.src.services.auth_service import AuthService
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.auth = AuthService()
        self.protected_prefixes = (
            "/chat",
            "/action",
            "/events",
            "/event",
            "/sessions",
            "/profile",
            "/usage",
            "/intel",
            "/audio",
            "/voice",
            "/tts",
        )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        if not self._is_protected(path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization") or ""
        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.info("AUTH_REJECTED path=%s reason=missing_or_invalid_bearer_header", path)
            return JSONResponse(status_code=401, content={"status": "error", "detail": "Unauthorized"})

        token = parts[1].strip()
        if not token:
            logger.info("AUTH_REJECTED path=%s reason=empty_token", path)
            return JSONResponse(status_code=401, content={"status": "error", "detail": "Unauthorized"})
        try:
            services = getattr(request.app.state, "services", None)
            auth_service = getattr(services, "auth", None) or self.auth
            verified = auth_service.verify_token(token)
            request.state.user_id = verified["user_id"]
        except Exception as exc:
            logger.info("AUTH_REJECTED path=%s reason=token_verify_failed error=%s", path, exc)
            return JSONResponse(status_code=401, content={"status": "error", "detail": "Unauthorized"})
        logger.info("AUTH_ACCEPTED path=%s user_id=%s", path, request.state.user_id)
        return await call_next(request)

    def _is_protected(self, path: str) -> bool:
        for prefix in self.protected_prefixes:
            if path == prefix or path.startswith(f"{prefix}/"):
                return True
        return False
