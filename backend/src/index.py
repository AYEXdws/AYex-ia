from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.src.middleware.auth_middleware import AuthMiddleware
from backend.src.routes.action import router as action_router
from backend.src.routes.auth import router as auth_router
from backend.src.routes.chat import router as chat_router
from backend.src.routes.events import router as events_router
from backend.src.routes.health import router as health_router
from backend.src.routes.history import router as history_router
from backend.src.routes.profile import router as profile_router
from backend.src.routes.usage import router as usage_router
from backend.src.services.container import build_services
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
API_PREFIXES = ("/auth", "/chat", "/action", "/events", "/health", "/sessions", "/profile", "/usage", "/audio", "/voice", "/tts", "/event")

app = FastAPI(title="AYEX Backend", version="0.2.0")
app.add_middleware(AuthMiddleware)
app.state.services = build_services()

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(action_router)
app.include_router(history_router)
app.include_router(profile_router)
app.include_router(usage_router)
app.include_router(events_router)

if not app.state.services.settings.web_mvp_only:
    from backend.src.routes.audio import router as audio_router
    from backend.src.routes.event import router as event_router
    from backend.src.routes.tts import router as tts_router

    app.include_router(audio_router)
    app.include_router(tts_router)
    app.include_router(event_router)

if FRONTEND_DIST.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_fallback(full_path: str):
        normalized = f"/{full_path}" if full_path else "/"
        if normalized.startswith(API_PREFIXES):
            return FileResponse(str(FRONTEND_INDEX), status_code=404)
        target = (FRONTEND_DIST / full_path).resolve()
        # Serve real asset files directly; fallback to SPA index otherwise.
        if str(target).startswith(str(FRONTEND_DIST.resolve())) and target.exists() and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(FRONTEND_INDEX))

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    logger.warning("frontend_dist_missing path=%s", FRONTEND_DIST)

logger.info("backend_initialized")
