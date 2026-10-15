"""
backend/main.py — FastAPI Application Entry Point for SAIL YANTRA.
==================================================================
Production-grade ASGI application exposing:
  • /api/market/*     — TinyFish-powered BDI & Bunker Fuel endpoints
  • /api/optimizer/*  — ML chartering & freight prediction pipeline
  • /api/health       — System health and status check
  • /docs & /redoc    — Interactive OpenAPI documentation
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.routers.market import market_router
from backend.routers.optimizer_routes import optimizer_router
from backend.services.cache_service import cache_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sail_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown management."""
    logger.info("Initializing %s v%s...", settings.APP_NAME, settings.APP_VERSION)
    logger.info("TinyFish Base URL: %s", settings.TINYFISH_BASE_URL)
    if settings.TINYFISH_API_KEY:
        masked = settings.TINYFISH_API_KEY[:4] + "..." + settings.TINYFISH_API_KEY[-4:]
        logger.info("TinyFish API Key configured (%s)", masked)
    else:
        logger.warning(
            "TINYFISH_API_KEY is not configured. Serving cached baseline data until key is provided."
        )

    # Validate cache existence
    status = await cache_service.get_sync_status()
    logger.info(
        "Market cache status: BDI=%s, Bunker=%s",
        status["bdi_freshness"],
        status["bunker_freshness"],
    )

    yield

    logger.info("Shutting down %s...", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production backend integration for SAIL YANTRA. Integrates TinyFish autonomous web agents "
        "for continuous extraction and normalization of Baltic Dry Index (BDI) and marine bunker fuel "
        "prices, seamlessly feeding live market intelligence into the predictive chartering ML pipeline."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────────────────────
# CORS CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if "*" not in settings.CORS_ORIGINS else ["*"],
    allow_credentials=True if "*" not in settings.CORS_ORIGINS else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(market_router)
app.include_router(optimizer_router)


# ─────────────────────────────────────────────────────────────────────────────
# BASE / HEALTH ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", tags=["System"])
async def root():
    """Application index returning service metadata and documentation links."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "documentation": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "bdi": "/api/market/bdi",
            "bunker_prices": "/api/market/bunker-prices",
            "market_sync": "/api/market/sync",
            "sync_status": "/api/market/sync/status",
            "market_summary": "/api/market/summary",
            "live_optimizer_params": "/api/optimizer/live-params",
            "run_optimization": "/api/optimizer/run",
            "health": "/api/health",
        },
    }


@app.get("/api/health", tags=["System"])
async def health_check():
    """Health check endpoint for container probes and uptime monitors."""
    sync_status = await cache_service.get_sync_status()
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "tinyfish_configured": bool(settings.TINYFISH_API_KEY),
        "bdi_freshness": sync_status["bdi_freshness"],
        "bunker_freshness": sync_status["bunker_freshness"],
        "cache_persisted": sync_status["cache_file_exists"],
    }
