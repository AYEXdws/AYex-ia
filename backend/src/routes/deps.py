from __future__ import annotations

from fastapi import Request

from backend.src.services.container import BackendServices


def get_services(request: Request) -> BackendServices:
    return request.app.state.services  # type: ignore[attr-defined]
