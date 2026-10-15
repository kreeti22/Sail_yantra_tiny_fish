"""
backend/routers/optimizer_routes.py — FastAPI routes for ML Optimizer & Prediction Pipeline.
=============================================================================================
Exposes:
  • GET  /api/optimizer/live-params — Live market parameters tailored for optimizer models
  • POST /api/optimizer/run         — Runs full ML optimization pipeline using live TinyFish intelligence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.services.ml_adapter import ml_adapter

logger = logging.getLogger("optimizer_routes")
logger.setLevel(logging.INFO)

optimizer_router = APIRouter(prefix="/api/optimizer", tags=["ML Maritime Optimizer"])


class OptimizationRequest(BaseModel):
    """Voyage inputs for the ML chartering and freight optimizer."""
    route: str = Field(default="Dampier, Australia - Visakhapatnam", description="Origin - Destination route")
    cargo_type: str = Field(default="Coal Ore", description="Commodity type")
    vessel_class: str = Field(default="Panamax", description="Vessel size category")
    market_event: str = Field(default="None", description="Geopolitical or market shock event")
    vessel_dwt: float = Field(default=78000.0, description="Vessel deadweight tonnage (DWT)")
    distance_nm: float = Field(default=3570.0, description="Voyage distance in nautical miles")
    port_congestion_days: float = Field(default=1.5, description="Expected waiting time at discharge port")
    port: str = Field(default="Vizag", description="Discharge port name")
    cargo_tonnes: float = Field(default=60000.0, description="Cargo quantity in metric tonnes")
    required_days: float = Field(default=30.0, description="Laycan or required delivery window in days")
    wind_speed: float = Field(default=12.0, description="Wind speed in knots")
    wave_height: float = Field(default=2.0, description="Wave height in meters")
    speed: float = Field(default=14.0, description="Cruising speed in knots")
    vessel_age: float = Field(default=8.0, description="Vessel age in years")
    inventory_hold_cost_per_day: float = Field(default=12000.0, description="Inventory carrying cost USD/day")
    
    # Optional manual overrides (if None, live market intelligence is applied automatically)
    baltic_style_index: Optional[float] = Field(None, description="Optional manual override for BDI")
    bunker_fuel_price: Optional[float] = Field(None, description="Optional manual override for Bunker USD/MT")


@optimizer_router.get(
    "/live-params",
    summary="Get live market inputs for optimizer",
    description="Returns latest BDI and bunker prices formatted directly for ML model consumption.",
)
async def get_live_optimizer_params() -> Dict[str, Any]:
    """Retrieve current live parameters ready for the ML pipeline."""
    return await ml_adapter.get_live_market_inputs()


@optimizer_router.post(
    "/run",
    summary="Execute full maritime optimization pipeline",
    description="Executes FreightXGB, FuelXGB, TimingEnsemble, and VesselRanker using live TinyFish intelligence.",
)
async def run_optimization(
    request: OptimizationRequest,
    use_live_market: bool = Query(True, description="Inject live TinyFish BDI & Bunker quotes automatically"),
) -> Dict[str, Any]:
    """Execute optimization with live market intelligence."""
    try:
        payload = request.model_dump()
        result = await ml_adapter.run_adapted_optimization(
            params=payload,
            use_live_market=use_live_market,
        )

        # Ensure all numpy/pandas objects in result are JSON serializable
        return _make_json_serializable(result)
    except Exception as e:
        logger.error("Error executing optimization pipeline: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization execution failed: {str(e)}",
        )


def _make_json_serializable(obj: Any) -> Any:
    """Recursively converts numpy types and DataFrames to JSON-compatible Python primitives."""
    import numpy as np
    import pandas as pd

    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_json_serializable(v) for v in obj]
    elif isinstance(obj, tuple):
        return [_make_json_serializable(v) for v in obj]
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    elif isinstance(obj, pd.Series):
        return obj.to_dict()
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj
