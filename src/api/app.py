"""FastAPI application factory for CPBL Analytics."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import analysis, games, players

_DASHBOARD_DIR = Path(__file__).parent.parent.parent / "dashboard" / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="CPBL Analytics API",
        description=(
            "進階棒球數據分析 API — LOB%、Leverage Index、Count Splits、Pitcher Fatigue。"
            " 基於 Rebas Open Data + CPBL 官網公開資料。"
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS (open for demo / dashboard) ──────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────
    app.include_router(players.router)
    app.include_router(games.router)
    app.include_router(analysis.router)

    # ── Static dashboard ──────────────────────────────────────────
    if _DASHBOARD_DIR.exists():
        app.mount(
            "/dashboard",
            StaticFiles(directory=str(_DASHBOARD_DIR), html=True),
            name="dashboard",
        )

    # ── Health check ──────────────────────────────────────────────
    @app.get("/health", tags=["meta"], include_in_schema=False)
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "cpbl-analytics"})

    return app
