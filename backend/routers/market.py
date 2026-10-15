"""
backend/routers/market.py — FastAPI routes for Maritime Market Intelligence.
=============================================================================
Endpoints:
  • GET  /api/market/bdi            — Latest Baltic Dry Index data
  • GET  /api/market/bunker-prices  — Latest marine bunker fuel prices
  • POST /api/market/sync           — Trigger manual synchronization (protected & debounced)
  • GET  /api/market/sync/status    — Synchronization status and health info
  • GET  /api/market/summary        — Combined market overview for frontend dashboard
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from backend.config import settings
from backend.schemas.market import (
    BDIData,
    BDIResponse,
    BunkerPricesData,
    BunkerPricesResponse,
    MarketSummaryResponse,
    SyncRequest,
    SyncResponse,
    SyncStatusResponse,
)
from backend.services.bdi_service import bdi_service
from backend.services.bunker_service import bunker_service
from backend.services.cache_service import cache_service

logger = logging.getLogger("market_router")
logger.setLevel(logging.INFO)

market_router = APIRouter(prefix="/api/market", tags=["Maritime Market Intelligence"])


# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION / TOKEN GUARD FOR SYNC
# ─────────────────────────────────────────────────────────────────────────────
def verify_sync_permission(
    x_sync_token: Optional[str] = Header(None, alias="X-Sync-Token"),
    authorization: Optional[str] = Header(None),
) -> bool:
    """
    If SYNC_SECRET_TOKEN is set in environment, validates header or Bearer token.
    If no token is set in environment, allows requests (development mode).
    """
    secret = settings.SYNC_SECRET_TOKEN
    if not secret:
        return True  # Open in dev / local mode

    # Check X-Sync-Token header
    if x_sync_token and x_sync_token.strip() == secret:
        return True

    # Check Authorization: Bearer <token>
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == secret:
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Valid X-Sync-Token or Bearer token required for manual synchronization.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────
@market_router.get(
    "/bdi",
    response_model=BDIResponse,
    summary="Retrieve latest Baltic Dry Index",
    description="Returns the latest BDI quote, daily changes, reporting date, freshness metadata, and source URL.",
)
async def get_bdi(
    force_refresh: bool = Query(
        False,
        description="If True, bypasses cache and triggers fresh TinyFish extraction (subject to API key availability).",
    )
) -> BDIResponse:
    """Fetch latest Baltic Dry Index quote."""
    return await bdi_service.get_latest_bdi(force_refresh=force_refresh)


@market_router.get(
    "/bunker-prices",
    response_model=BunkerPricesResponse,
    summary="Retrieve latest marine bunker fuel prices",
    description="Returns port-specific bunker fuel quotes (VLSFO, HSFO, MGO) and the primary Singapore benchmark.",
)
async def get_bunker_prices(
    force_refresh: bool = Query(
        False,
        description="If True, bypasses cache and triggers fresh TinyFish extraction.",
    )
) -> BunkerPricesResponse:
    """Fetch latest bunker fuel prices."""
    return await bunker_service.get_latest_bunker_prices(force_refresh=force_refresh)


@market_router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Trigger manual market-data synchronization",
    description="Synchronizes BDI and bunker fuel quotes via TinyFish. Protected against concurrent runs and rapid spam.",
)
async def trigger_manual_sync(
    request: SyncRequest = SyncRequest(),
    authorized: bool = Depends(verify_sync_permission),
) -> SyncResponse:
    """Manually trigger background or immediate synchronization."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Check debounce / rate limit
    can_sync, reason = await cache_service.can_trigger_sync()
    if not can_sync and not request.force:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=reason,
        )

    # Check concurrent lock
    if cache_service.sync_lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A synchronization process is already active. Please wait for completion.",
        )

    async with cache_service.sync_lock:
        await cache_service.set_sync_in_progress(True)
        errors: List[str] = []
        bdi_updated = False
        bunker_updated = False

        target = request.target.lower()

        # 1. BDI Sync
        if target in ("all", "bdi"):
            try:
                bdi_res = await bdi_service.fetch_live_bdi()
                bdi_updated = (bdi_res.status == "success")
            except Exception as e:
                err_msg = f"BDI Sync failed: {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)
                await cache_service.record_bdi_failure(str(e))

        # 2. Bunker Sync
        if target in ("all", "bunker"):
            try:
                bunker_res = await bunker_service.fetch_live_bunker_prices()
                bunker_updated = (bunker_res.status == "success")
            except Exception as e:
                err_msg = f"Bunker Sync failed: {str(e)}"
                logger.error(err_msg)
                errors.append(err_msg)
                await cache_service.record_bunker_failure(str(e))

        final_err = "; ".join(errors) if errors else None
        await cache_service.set_sync_in_progress(False, error=final_err)

    status_str = "success" if not errors else ("partial_success" if (bdi_updated or bunker_updated) else "error")
    msg = "Manual synchronization completed successfully." if not errors else f"Sync completed with issues: {final_err}"

    # Get freshness indicators
    _, bdi_fresh, _, _ = await cache_service.get_bdi()
    _, bunker_fresh, _, _ = await cache_service.get_bunker()

    return SyncResponse(
        status=status_str,
        message=msg,
        triggered_at=now_iso,
        bdi_updated=bdi_updated,
        bunker_updated=bunker_updated,
        bdi_freshness=bdi_fresh,
        bunker_freshness=bunker_fresh,
        errors=errors,
    )


@market_router.get(
    "/sync/status",
    response_model=SyncStatusResponse,
    summary="Retrieve market data synchronization status",
    description="Returns current sync status, freshness metrics, last execution timestamps, and API key configuration.",
)
async def get_sync_status() -> SyncStatusResponse:
    """Fetch status of cache and synchronization health."""
    stat = await cache_service.get_sync_status()
    return SyncStatusResponse(
        status="degraded" if stat.get("last_error") else "healthy",
        is_syncing=stat["is_syncing"],
        last_sync_attempt=stat["last_sync_attempt"],
        last_successful_sync=stat["last_successful_sync"],
        bdi_freshness=stat["bdi_freshness"],
        bdi_last_extracted=stat["bdi_last_extracted"],
        bunker_freshness=stat["bunker_freshness"],
        bunker_last_extracted=stat["bunker_last_extracted"],
        cache_file_exists=stat["cache_file_exists"],
        api_key_configured=stat["api_key_configured"],
        last_error=stat["last_error"],
    )


@market_router.get(
    "/summary",
    response_model=MarketSummaryResponse,
    summary="Combined market intelligence summary",
    description="Aggregated view providing current BDI, bunker benchmarks, and ML model readiness for dashboard cards.",
)
async def get_market_summary() -> MarketSummaryResponse:
    """Combined summary of all market intelligence feeds."""
    bdi_res = await bdi_service.get_latest_bdi()
    bunker_res = await bunker_service.get_latest_bunker_prices()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return MarketSummaryResponse(
        status="success",
        bdi=bdi_res,
        bunker=bunker_res,
        ml_ready=True,
        timestamp=now_iso,
    )
