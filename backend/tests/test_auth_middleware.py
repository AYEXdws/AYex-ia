from __future__ import annotations

import asyncio
from types import SimpleNamespace

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.src.middleware.auth_middleware import AuthMiddleware


async def _next(_request: Request):
    return JSONResponse({"ok": True})


def _build_request(path: str, headers: dict[str, str], expected_token: str = "secret-token") -> Request:
    app = Starlette()
    app.state.services = SimpleNamespace(
        settings=SimpleNamespace(intel_ingest_token=expected_token),
        auth=SimpleNamespace(verify_token=lambda token: {"user_id": "ayex", "payload": {"sub": token}}),
    )
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in headers.items()],
        "app": app,
        "client": ("127.0.0.1", 12345),
        "query_string": b"",
    }
    return Request(scope)


def test_auth_middleware_accepts_ingest_token_for_events(monkeypatch):
    monkeypatch.setenv("AYEX_JWT_SECRET", "test-secret")
    request = _build_request("/events/ingest", {"x-ayex-ingest-token": "secret-token"})
    middleware = AuthMiddleware(app=request.app)

    response = asyncio.run(middleware.dispatch(request, _next))

    assert response.status_code == 200


def test_auth_middleware_rejects_missing_bearer_on_chat(monkeypatch):
    monkeypatch.setenv("AYEX_JWT_SECRET", "test-secret")
    request = _build_request("/chat", {})
    middleware = AuthMiddleware(app=request.app)

    response = asyncio.run(middleware.dispatch(request, _next))

    assert response.status_code == 401
