from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.core.config import Settings, get_settings
from app.core.repository import LocalJobRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(title="AI Reviewer Agent", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.jobs = LocalJobRepository(resolved_settings.object_storage_path)
    app.include_router(health_router)
    app.include_router(jobs_router)
    return app


app = create_app()
