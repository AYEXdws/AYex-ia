from __future__ import annotations

from fastapi import FastAPI

from backend.src.routes.action import router as action_router
from backend.src.routes.chat import router as chat_router
from backend.src.routes.health import router as health_router
from backend.src.routes.web import router as web_router
from backend.src.services.container import build_services
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)

app = FastAPI(title="AYEX Backend", version="0.2.0")
app.state.services = build_services()

app.include_router(health_router)
app.include_router(web_router)
app.include_router(chat_router)
app.include_router(action_router)

if not app.state.services.settings.web_mvp_only:
    from backend.src.routes.audio import router as audio_router
    from backend.src.routes.event import router as event_router
    from backend.src.routes.tts import router as tts_router

    app.include_router(audio_router)
    app.include_router(tts_router)
    app.include_router(event_router)

logger.info("backend_initialized")
