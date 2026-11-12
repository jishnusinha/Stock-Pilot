"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.core.config import settings
from app.db.connection import connect
from app.db.migrations import migrate


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.ensure_dirs()
    conn = connect()
    try:
        migrate(conn)
    finally:
        conn.close()
    yield


app = FastAPI(
    title="StockPilot API",
    version=__version__,
    description="Local inventory intelligence — no LLM. Synthetic demo data.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "app": "StockPilot",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/health",
        "note": "Demo Mode · SYNTHETIC_DEMO · no LLM",
    }
