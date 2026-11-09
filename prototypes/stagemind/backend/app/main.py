"""FastAPI 入口：组装路由、静态资源与生命周期。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import blocking, issues, logs, rehearsals, search, upload
from app.config import settings
from app.core.db import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(rehearsals.router, prefix="/api")
    app.include_router(upload.router, prefix="/api")
    app.include_router(logs.router, prefix="/api")
    app.include_router(blocking.router, prefix="/api")
    app.include_router(issues.router, prefix="/api")
    app.include_router(search.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.frontend_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(settings.frontend_dir), html=True),
            name="frontend",
        )
    return app


app = create_app()
