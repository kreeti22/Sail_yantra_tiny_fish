"""
backend/schemas/market.py — Pydantic models for BDI, Bunker Fuel, and Sync endpoints.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class BDIData(BaseModel):
    """Normalized Baltic Dry Index data."""
    index_name: str = Field(default="Baltic Dry Index", description="Name of the index")
    value: float = Field(..., gt=0, lt=50000, description="Current BDI index value")
    daily_change: Optional[float] = Field(None, description="Absolute daily change in points")
    daily_change_pct: Optional[float] = Field(None, description="Percentage daily change")
    reporting_date: str = Field(..., description="Reporting date formatted as YYYY-MM-DD or market date string")
    unit: str = Field(default="points", description="Index measurement unit")


class BDIResponse(BaseModel):
    """Response payload for GET /api/market/bdi."""
    status: str = Field(..., description="'success', 'stale', 'fallback', or 'error'")
    freshness: str = Field(..., description="'fresh', 'stale', or 'fallback'")
    data: BDIData
    extracted_at: Optional[str] = Field(None, description="ISO timestamp when TinyFish extracted this data")
    source_url: str = Field(..., description="Legitimate public source URL")
    message: Optional[str] = Field(None, description="Informational or degradation notice")


class BunkerFuelPrice(BaseModel):
    """Normalized bunker fuel quote for a specific port and grade."""
    port_name: str = Field(..., description="Port name, e.g., Singapore, Rotterdam, Fujairah")
    fuel_grade: str = Field(..., description="Fuel grade: VLSFO, HSFO (IFO380), or MGO")
    price_usd_per_mt: float = Field(..., gt=50, lt=5000, description="Price in USD per Metric Ton")
    daily_change: Optional[float] = Field(None, description="Price change relative to previous session")
    currency: str = Field(default="USD", description="Currency of quote")
    unit: str = Field(default="USD/MT", description="Unit of measurement")
    reporting_date: Optional[str] = Field(None, description="Date of price reporting")


class BunkerBenchmark(BaseModel):
    """Primary benchmark bunker price used for freight model calculations."""
    port_name: str = Field(default="Singapore", description="Benchmark reference port")
    fuel_grade: str = Field(default="VLSFO", description="Benchmark reference fuel grade")
    price_usd_per_mt: float = Field(..., description="Benchmark price USD/MT")
    reporting_date: Optional[str] = Field(None, description="Benchmark date")


class BunkerPricesData(BaseModel):
    """Bunker prices payload containing benchmark and port quotes."""
    benchmark: BunkerBenchmark
    ports: List[BunkerFuelPrice]


class BunkerPricesResponse(BaseModel):
    """Response payload for GET /api/market/bunker-prices."""
    status: str = Field(..., description="'success', 'stale', 'fallback', or 'error'")
    freshness: str = Field(..., description="'fresh', 'stale', or 'fallback'")
    data: BunkerPricesData
    extracted_at: Optional[str] = Field(None, description="ISO timestamp of extraction")
    source_url: str = Field(..., description="Source URL")
    message: Optional[str] = Field(None, description="Informational notice")


class SyncRequest(BaseModel):
    """Request payload for manual synchronization."""
    target: str = Field(default="all", description="'all', 'bdi', or 'bunker'")
    force: bool = Field(default=False, description="Bypass cache TTL if true")


class SyncResponse(BaseModel):
    """Response payload for POST /api/market/sync."""
    status: str = Field(..., description="'success', 'partial_success', 'rate_limited', or 'error'")
    message: str = Field(..., description="Status summary")
    triggered_at: str = Field(..., description="ISO timestamp")
    bdi_updated: bool = Field(default=False)
    bunker_updated: bool = Field(default=False)
    bdi_freshness: str = Field(default="unknown")
    bunker_freshness: str = Field(default="unknown")
    errors: List[str] = Field(default_factory=list)


class SyncStatusResponse(BaseModel):
    """Response payload for GET /api/market/sync/status."""
    status: str = Field(default="healthy")
    is_syncing: bool = Field(default=False, description="True if a sync job is currently active")
    last_sync_attempt: Optional[str] = Field(None)
    last_successful_sync: Optional[str] = Field(None)
    bdi_freshness: str = Field(default="unknown")
    bdi_last_extracted: Optional[str] = Field(None)
    bunker_freshness: str = Field(default="unknown")
    bunker_last_extracted: Optional[str] = Field(None)
    cache_file_exists: bool = Field(default=False)
    api_key_configured: bool = Field(default=False)
    last_error: Optional[str] = Field(None)


class MarketSummaryResponse(BaseModel):
    """Aggregated market intelligence for the dashboard."""
    status: str = Field(default="success")
    bdi: BDIResponse
    bunker: BunkerPricesResponse
    ml_ready: bool = Field(default=True, description="Indicates if live data is ready for the ML optimizer")
    timestamp: str = Field(...)
