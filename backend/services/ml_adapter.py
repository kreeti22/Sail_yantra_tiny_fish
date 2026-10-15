"""
backend/services/ml_adapter.py — ML Prediction Pipeline & Market Data Adapter.
==============================================================================
Safely adapts live extracted BDI and Bunker Fuel market intelligence into the
existing SAIL YANTRA ML optimizer (optimizer.py) without altering trained model
feature schemas or dimensions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from backend.services.cache_service import cache_service

logger = logging.getLogger("ml_adapter")
logger.setLevel(logging.INFO)


class MLMarketAdapter:
    """
    Adapter between live extracted market intelligence and optimizer.py ML models.
    Preserves exact feature schema:
      - 'baltic_style_index' (Float)
      - 'bunker_fuel_price' (Float)
    """

    @staticmethod
    async def get_live_market_inputs() -> Dict[str, Any]:
        """
        Retrieves current BDI and Bunker benchmark values from the market cache.
        Returns normalized inputs and provenance metadata.
        """
        bdi_data, bdi_freshness, bdi_time, bdi_source = await cache_service.get_bdi()
        bunker_data, bunker_freshness, bunker_time, bunker_source = await cache_service.get_bunker()

        bdi_val = float(bdi_data.get("value", 1550.0))
        bunker_val = float(bunker_data.get("benchmark", {}).get("price_usd_per_mt", 640.0))

        return {
            "baltic_style_index": bdi_val,
            "bunker_fuel_price": bunker_val,
            "metadata": {
                "bdi": {
                    "value": bdi_val,
                    "freshness": bdi_freshness,
                    "extracted_at": bdi_time,
                    "source": bdi_source,
                },
                "bunker": {
                    "value": bunker_val,
                    "port": bunker_data.get("benchmark", {}).get("port_name", "Singapore"),
                    "grade": bunker_data.get("benchmark", {}).get("fuel_grade", "VLSFO"),
                    "freshness": bunker_freshness,
                    "extracted_at": bunker_time,
                    "source": bunker_source,
                },
            },
        }

    @classmethod
    async def run_adapted_optimization(
        cls,
        params: Dict[str, Any],
        use_live_market: bool = True,
    ) -> Dict[str, Any]:
        """
        Merges live market data into voyage parameters and calls optimizer.run_optimization.
        Does not mutate the caller's parameter dict.
        """
        import optimizer  # import existing module

        merged_params = dict(params)
        market_inputs = await cls.get_live_market_inputs()

        # If live market is enabled, inject into inputs unless caller provided an explicit override
        if use_live_market:
            if "baltic_style_index" not in merged_params or merged_params["baltic_style_index"] is None:
                merged_params["baltic_style_index"] = market_inputs["baltic_style_index"]
            if "bunker_fuel_price" not in merged_params or merged_params["bunker_fuel_price"] is None:
                merged_params["bunker_fuel_price"] = market_inputs["bunker_fuel_price"]

        # Run core ML optimization
        opt_result = optimizer.run_optimization(merged_params)

        # Attach market provenance
        opt_result["market_provenance"] = {
            "live_market_used": use_live_market,
            "applied_bdi": merged_params.get("baltic_style_index"),
            "applied_bunker_usd_mt": merged_params.get("bunker_fuel_price"),
            "market_metadata": market_inputs["metadata"],
        }

        return opt_result


ml_adapter = MLMarketAdapter()
