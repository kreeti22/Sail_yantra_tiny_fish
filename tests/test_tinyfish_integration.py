"""
tests/test_tinyfish_integration.py — Complete Automated Test Suite.
===================================================================
Tests all 12 requirements specified in Task 1:
  1.  TinyFish client authentication configuration
  2.  Successful BDI extraction and parsing
  3.  Successful bunker fuel price extraction and parsing
  4.  Invalid extraction responses handling
  5.  Missing API key handling
  6.  Network timeout handling
  7.  API rate-limit responses (HTTP 429 & backoff)
  8.  Cache retrieval
  9.  Stale cache behavior
  10. Manual synchronization endpoint
  11. Concurrent synchronization protection (HTTP 409)
  12. Existing backend API / ML compatibility
"""

import asyncio
import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.schemas.market import BDIData, BunkerPricesData
from backend.services.bdi_service import BDIService, bdi_service
from backend.services.bunker_service import BunkerService, bunker_service
from backend.services.cache_service import MarketCacheService, cache_service
from backend.services.ml_adapter import ml_adapter
from backend.services.tinyfish_client import (
    TinyFishAuthError,
    TinyFishClient,
    TinyFishError,
    TinyFishExtractionError,
    TinyFishMissingKeyError,
    TinyFishRateLimitError,
    TinyFishTimeoutError,
)

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# 1. CLIENT AUTHENTICATION CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
def test_1_client_auth_configuration():
    """Confirms TinyFishClient initializes headers correctly and protects secrets."""
    c = TinyFishClient(api_key="tf_live_secret_key_12345")
    assert c.is_configured() is True
    headers = c._get_headers()
    assert headers["X-API-Key"] == "tf_live_secret_key_12345"
    assert headers["Content-Type"] == "application/json"
    assert "User-Agent" in headers

    # Unconfigured client
    c_empty = TinyFishClient(api_key="")
    assert c_empty.is_configured() is False
    with pytest.raises(TinyFishMissingKeyError):
        c_empty._get_headers()


# ─────────────────────────────────────────────────────────────────────────────
# 2. SUCCESSFUL BDI EXTRACTION AND PARSING
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_2_successful_bdi_extraction_and_parsing():
    """Confirms BDI service accurately validates and normalizes real-world TinyFish output."""
    mock_tinyfish = MagicMock(spec=TinyFishClient)
    mock_tinyfish.run_extraction = AsyncMock(return_value={
        "status": "COMPLETED",
        "run_id": "run_bdi_test_001",
        "result": {
            "index_name": "Baltic Dry Index",
            "value": 1845.0,
            "daily_change": 23.5,
            "daily_change_pct": 1.29,
            "reporting_date": "2026-10-14",
            "unit": "points",
        },
    })

    service = BDIService(client=mock_tinyfish)
    res = await service.fetch_live_bdi()

    assert res.status == "success"
    assert res.freshness == "fresh"
    assert res.data.value == 1845.0
    assert res.data.daily_change == 23.5
    assert res.data.daily_change_pct == 1.29
    assert res.data.reporting_date == "2026-10-14"
    assert res.data.unit == "points"
    assert res.source_url == settings.BDI_SOURCE_URL


# ─────────────────────────────────────────────────────────────────────────────
# 3. SUCCESSFUL BUNKER FUEL PRICE EXTRACTION AND PARSING
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_3_successful_bunker_fuel_price_extraction_and_parsing():
    """Confirms bunker fuel service normalizes ports, grades (VLSFO, HSFO, MGO), and benchmarks."""
    mock_tinyfish = MagicMock(spec=TinyFishClient)
    mock_tinyfish.run_extraction = AsyncMock(return_value={
        "status": "COMPLETED",
        "run_id": "run_bunker_test_002",
        "result": {
            "ports": [
                {
                    "port_name": "Singapore Port",
                    "fuel_grade": "VLSFO 0.5%",
                    "price_usd_per_mt": 648.5,
                    "daily_change": -3.0,
                    "currency": "USD",
                    "unit": "USD/MT",
                    "reporting_date": "2026-10-14",
                },
                {
                    "port_name": "Singapore",
                    "fuel_grade": "IFO 380",
                    "price_usd_per_mt": 492.0,
                    "daily_change": 1.5,
                    "currency": "USD",
                    "unit": "USD/MT",
                    "reporting_date": "2026-10-14",
                },
                {
                    "port_name": "Rotterdam",
                    "fuel_grade": "MGO",
                    "price_usd_per_mt": 810.0,
                    "daily_change": -5.0,
                    "currency": "USD",
                    "unit": "USD/MT",
                    "reporting_date": "2026-10-14",
                },
            ]
        },
    })

    service = BunkerService(client=mock_tinyfish)
    res = await service.fetch_live_bunker_prices()

    assert res.status == "success"
    assert res.freshness == "fresh"
    assert len(res.data.ports) == 3

    # Verify normalization
    quotes = { (q.port_name, q.fuel_grade): q.price_usd_per_mt for q in res.data.ports }
    assert ("Singapore", "VLSFO") in quotes
    assert quotes[("Singapore", "VLSFO")] == 648.5
    assert ("Singapore", "HSFO") in quotes
    assert quotes[("Singapore", "HSFO")] == 492.0
    assert ("Rotterdam", "MGO") in quotes

    # Benchmark check: Singapore VLSFO should be selected
    assert res.data.benchmark.port_name == "Singapore"
    assert res.data.benchmark.fuel_grade == "VLSFO"
    assert res.data.benchmark.price_usd_per_mt == 648.5


# ─────────────────────────────────────────────────────────────────────────────
# 4. INVALID EXTRACTION RESPONSES
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_4_invalid_extraction_responses():
    """Confirms malformed or out-of-bounds agent responses are rejected."""
    service = BDIService()

    # Out of bounds BDI (e.g. 500,000)
    with pytest.raises(ValueError, match="outside valid market parameters"):
        service._validate_and_normalize({"value": 500000.0})

    # Non-numeric BDI
    with pytest.raises(ValueError, match="BDI numeric value missing"):
        service._validate_and_normalize({"index_name": "BDI"})

    # Bunker missing ports list
    bunker_svc = BunkerService()
    with pytest.raises(ValueError, match="missing valid 'ports' array"):
        bunker_svc._validate_and_normalize({"unknown": 123})


# ─────────────────────────────────────────────────────────────────────────────
# 5. MISSING API KEY HANDLING
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_5_missing_api_key():
    """Confirms missing API key degrades gracefully to cached or fallback baseline."""
    client_unconfigured = TinyFishClient(api_key="")
    bdi_svc = BDIService(client=client_unconfigured)
    bunker_svc = BunkerService(client=client_unconfigured)

    # Calling fetch directly raises TinyFishMissingKeyError
    with pytest.raises(TinyFishMissingKeyError):
        await bdi_svc.fetch_live_bdi()

    # Calling get_latest_bdi returns fallback/stale without crash
    res_bdi = await bdi_svc.get_latest_bdi(force_refresh=True)
    assert res_bdi.status in ("fallback", "stale")
    assert res_bdi.data.value > 0

    res_bunker = await bunker_svc.get_latest_bunker_prices(force_refresh=True)
    assert res_bunker.status in ("fallback", "stale")
    assert res_bunker.data.benchmark.price_usd_per_mt > 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. NETWORK TIMEOUT HANDLING
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_6_network_timeout():
    """Confirms TinyFishTimeoutError is raised when requests exceed configured timeouts."""
    client_timeout = TinyFishClient(api_key="test_key", request_timeout=0.01, max_retries=1)

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
        with pytest.raises(TinyFishTimeoutError):
            await client_timeout.run_extraction("https://example.com", "goal")


# ─────────────────────────────────────────────────────────────────────────────
# 7. API RATE LIMIT RESPONSES
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_7_rate_limit_responses():
    """Confirms client respects HTTP 429 rate limit errors and reports backoff."""
    client_rl = TinyFishClient(api_key="test_key", max_retries=1)

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "1"}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        with pytest.raises(TinyFishRateLimitError):
            await client_rl.run_extraction("https://example.com", "goal")


# ─────────────────────────────────────────────────────────────────────────────
# 8. CACHE RETRIEVAL
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_8_cache_retrieval():
    """Confirms fresh cached data is served instantly without contacting the network."""
    test_cache = MarketCacheService()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    await test_cache.save_bdi(
        data={"index_name": "Baltic Dry Index", "value": 1720.0, "reporting_date": "2026-10-14", "unit": "points"},
        source_url="https://test.com/bdi",
        extracted_at=now_iso,
    )

    data, freshness, extracted_at, src = await test_cache.get_bdi()
    assert freshness == "fresh"
    assert data["value"] == 1720.0
    assert src == "https://test.com/bdi"


# ─────────────────────────────────────────────────────────────────────────────
# 9. STALE CACHE BEHAVIOR
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_9_stale_cache_behavior():
    """Confirms data older than TTL is marked 'stale' while preserving previous values."""
    test_cache = MarketCacheService(ttl_seconds=3600)  # 1 hour TTL
    # 5 hours old
    old_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).isoformat()

    await test_cache.save_bdi(
        data={"index_name": "Baltic Dry Index", "value": 1600.0, "reporting_date": "2026-10-10", "unit": "points"},
        source_url="https://test.com/bdi",
        extracted_at=old_iso,
    )

    data, freshness, extracted_at, src = await test_cache.get_bdi()
    assert freshness == "stale"
    assert data["value"] == 1600.0


# ─────────────────────────────────────────────────────────────────────────────
# 10. MANUAL SYNCHRONIZATION ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────
def test_10_manual_synchronization():
    """Confirms POST /api/market/sync endpoint triggers synchronization."""
    with patch("backend.services.bdi_service.bdi_service.fetch_live_bdi") as mock_bdi, \
         patch("backend.services.bunker_service.bunker_service.fetch_live_bunker_prices") as mock_bunker:

        mock_bdi.return_value = MagicMock(status="success")
        mock_bunker.return_value = MagicMock(status="success")

        resp = client.post("/api/market/sync", json={"target": "all", "force": True})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] in ("success", "partial_success")
        assert payload["bdi_updated"] is True
        assert payload["bunker_updated"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 11. CONCURRENT SYNCHRONIZATION PROTECTION
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_11_concurrent_synchronization_protection():
    """Confirms concurrent sync calls receive HTTP 409 Conflict."""
    async with cache_service.sync_lock:
        # While lock is acquired, call sync endpoint
        response = client.post("/api/market/sync", json={"target": "all", "force": True})
        assert response.status_code == 409
        assert "already active" in response.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# 12. EXISTING BACKEND / ML COMPATIBILITY
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_12_existing_ml_backend_compatibility():
    """
    Confirms live market intelligence integrates seamlessly with optimizer.py:
    ML prediction pipeline runs and returns valid TLC, Net Savings, and Decision.
    """
    test_params = {
        "route": "Dampier, Australia - Visakhapatnam",
        "cargo_type": "Coal Ore",
        "vessel_class": "Panamax",
        "market_event": "None",
        "vessel_dwt": 78000,
        "distance_nm": 3570,
        "port_congestion_days": 1.5,
        "port": "Vizag",
        "cargo_tonnes": 60000,
        "required_days": 30,
        "wind_speed": 12.0,
        "wave_height": 2.0,
        "speed": 14.0,
        "vessel_age": 8,
        "inventory_hold_cost_per_day": 12000,
    }

    result = await ml_adapter.run_adapted_optimization(test_params, use_live_market=True)

    assert "decision" in result
    assert "tlc_breakdown" in result
    assert "net_savings_usd" in result
    assert "market_provenance" in result
    assert result["market_provenance"]["live_market_used"] is True
    assert result["market_provenance"]["applied_bdi"] > 0
    assert result["market_provenance"]["applied_bunker_usd_mt"] > 0

    # Test FastAPI optimizer route
    api_resp = client.post("/api/optimizer/run", json=test_params)
    assert api_resp.status_code == 200
    api_data = api_resp.json()
    assert "decision" in api_data
    assert "tlc_breakdown" in api_data
