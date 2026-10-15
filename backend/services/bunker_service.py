"""
backend/services/bunker_service.py — Marine Bunker Fuel Price TinyFish Ingestion Service.
========================================================================================
Features:
  • Official TinyFish agent extraction targeting public bunker fuel price sources
  • Multi-port extraction: Singapore, Rotterdam, Fujairah, Houston, Mumbai
  • Multi-grade extraction: VLSFO, HSFO (IFO380), MGO (never mixed)
  • Unit validation: USD per Metric Ton (USD/MT)
  • Benchmark calculation: Singapore VLSFO primary reference for freight calculations
  • Bounds checking and schema enforcement
  • Persistent caching with fallback preservation
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.schemas.market import (
    BunkerBenchmark,
    BunkerFuelPrice,
    BunkerPricesData,
    BunkerPricesResponse,
)
from backend.services.cache_service import cache_service
from backend.services.tinyfish_client import (
    TinyFishClient,
    TinyFishError,
    TinyFishMissingKeyError,
    tinyfish_client,
)

logger = logging.getLogger("bunker_service")
logger.setLevel(logging.INFO)

BUNKER_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "ports": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "port_name": {"type": "string", "description": "Port name (Singapore, Rotterdam, etc.)"},
                    "fuel_grade": {"type": "string", "description": "VLSFO, HSFO, or MGO"},
                    "price_usd_per_mt": {"type": "number", "description": "Price in USD per metric ton"},
                    "daily_change": {"type": "number", "description": "Price change from previous day"},
                    "currency": {"type": "string", "description": "USD"},
                    "unit": {"type": "string", "description": "USD/MT"},
                    "reporting_date": {"type": "string", "description": "Date of price quote"},
                },
                "required": ["port_name", "fuel_grade", "price_usd_per_mt"],
            },
        }
    },
    "required": ["ports"],
}

BUNKER_GOAL: str = (
    "Extract recent bunker fuel prices for major maritime bunkering hubs including Singapore and Rotterdam. "
    "For each port, extract quotes for fuel grades VLSFO, HSFO (or IFO380), and MGO in USD per metric ton (MT). "
    "Include port name, fuel grade, price in USD per MT, daily change, and reporting date. Return JSON."
)

ALLOWED_FUEL_GRADES = {"VLSFO", "HSFO", "MGO"}


class BunkerService:
    """Service for ingesting and validating marine bunker fuel prices."""

    def __init__(self, client: Optional[TinyFishClient] = None) -> None:
        self.client = client or tinyfish_client

    async def get_latest_bunker_prices(self, force_refresh: bool = False) -> BunkerPricesResponse:
        """
        Retrieves latest bunker fuel prices. Returns cached if fresh,
        or calls TinyFish to refresh.
        """
        cached_data, freshness, extracted_at, source_url = await cache_service.get_bunker()

        if freshness == "fresh" and not force_refresh:
            return BunkerPricesResponse(
                status="success",
                freshness="fresh",
                data=BunkerPricesData(**cached_data),
                extracted_at=extracted_at,
                source_url=source_url,
                message="Retrieved from fresh market cache.",
            )

        try:
            return await self.fetch_live_bunker_prices()
        except TinyFishMissingKeyError as mke:
            logger.info("TinyFish API key not configured: %s", mke)
            return BunkerPricesResponse(
                status="fallback" if freshness == "fallback" else "stale",
                freshness=freshness,
                data=BunkerPricesData(**cached_data),
                extracted_at=extracted_at,
                source_url=source_url,
                message="TINYFISH_API_KEY is not configured. Serving cached baseline bunker quotes.",
            )
        except Exception as e:
            logger.warning("Bunker prices live extraction failed: %s. Preserving previous data.", e)
            await cache_service.record_bunker_failure(str(e))
            return BunkerPricesResponse(
                status="stale",
                freshness="stale",
                data=BunkerPricesData(**cached_data),
                extracted_at=extracted_at,
                source_url=source_url,
                message=f"Live extraction failed ({str(e)}). Preserving last known valid bunker quotes.",
            )

    async def fetch_live_bunker_prices(self) -> BunkerPricesResponse:
        """Executes live extraction using TinyFish."""
        url = settings.BUNKER_SOURCE_URL

        logger.info("Initiating TinyFish Bunker fuel price extraction from %s", url)
        raw_result = await self.client.run_extraction(
            url=url,
            goal=BUNKER_GOAL,
            output_schema=BUNKER_OUTPUT_SCHEMA,
            browser_profile="lite",
        )

        extracted_data = raw_result.get("result", {})
        validated_data = self._validate_and_normalize(extracted_data)

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await cache_service.save_bunker(
            data=validated_data.model_dump(),
            source_url=url,
            extracted_at=now_iso,
        )

        return BunkerPricesResponse(
            status="success",
            freshness="fresh",
            data=validated_data,
            extracted_at=now_iso,
            source_url=url,
            message="Live bunker prices successfully ingested via TinyFish.",
        )

    def _validate_and_normalize(self, raw: Dict[str, Any]) -> BunkerPricesData:
        """Normalizes and validates raw agent output into BunkerPricesData."""
        if not isinstance(raw, dict):
            raise ValueError(f"Bunker extraction returned non-dict payload: {type(raw)}")

        raw_ports = raw.get("ports")
        if not raw_ports or not isinstance(raw_ports, list):
            # Check if raw itself is a list
            if isinstance(raw.get("result"), list):
                raw_ports = raw["result"]
            else:
                raise ValueError("Bunker extraction output missing valid 'ports' array.")

        validated_quotes: List[BunkerFuelPrice] = []
        today_str = datetime.date.today().isoformat()

        for item in raw_ports:
            if not isinstance(item, dict):
                continue

            port_name = str(item.get("port_name", "")).strip()
            if not port_name:
                continue

            # Standardize port name (e.g. "Singapore Port" -> "Singapore")
            port_name = self._normalize_port_name(port_name)

            # Fuel grade normalization
            raw_grade = str(item.get("fuel_grade", "")).strip().upper()
            fuel_grade = self._normalize_fuel_grade(raw_grade)
            if not fuel_grade:
                logger.debug("Skipping unrecognized fuel grade '%s' for port '%s'", raw_grade, port_name)
                continue

            # Price validation
            raw_price = item.get("price_usd_per_mt")
            if raw_price is None:
                raw_price = item.get("price")
            if raw_price is None:
                continue

            try:
                if isinstance(raw_price, str):
                    raw_price = float(re.sub(r"[^\d.-]", "", raw_price))
                price = float(raw_price)
            except (ValueError, TypeError):
                continue

            # Bounds check: Maritime bunker fuel historically $200 - $3000 / MT
            if price < 150 or price > 4500:
                logger.warning("Rejecting out-of-bounds bunker price $%.1f for %s %s", price, port_name, fuel_grade)
                continue

            # Currency check: only USD supported without explicit conversion
            curr = str(item.get("currency", "USD")).strip().upper()
            if curr not in ("USD", "$"):
                logger.warning("Rejecting non-USD price (%s) without exchange rate", curr)
                continue

            daily_change = None
            if item.get("daily_change") is not None:
                try:
                    daily_change = round(float(re.sub(r"[^\d.+-]", "", str(item["daily_change"]))), 2)
                except Exception:
                    pass

            rep_date = str(item.get("reporting_date", "")).strip() or today_str

            quote = BunkerFuelPrice(
                port_name=port_name,
                fuel_grade=fuel_grade,
                price_usd_per_mt=round(price, 2),
                daily_change=daily_change,
                currency="USD",
                unit="USD/MT",
                reporting_date=rep_date,
            )
            validated_quotes.append(quote)

        if not validated_quotes:
            raise ValueError("No valid bunker fuel quotes could be normalized from the extracted payload.")

        # Determine benchmark (Singapore VLSFO primary, Rotterdam VLSFO secondary, or first VLSFO quote)
        benchmark = self._select_benchmark(validated_quotes, today_str)

        return BunkerPricesData(
            benchmark=benchmark,
            ports=validated_quotes,
        )

    @staticmethod
    def _normalize_fuel_grade(raw_grade: str) -> Optional[str]:
        g = raw_grade.upper()
        if "VLSFO" in g or "0.5%" in g or "LOW SULFUR" in g:
            return "VLSFO"
        if "HSFO" in g or "IFO380" in g or "IFO 380" in g or "380 CST" in g or "3.5%" in g:
            return "HSFO"
        if "MGO" in g or "GAS OIL" in g or "GASOIL" in g or "DMA" in g:
            return "MGO"
        return None

    @staticmethod
    def _normalize_port_name(name: str) -> str:
        clean = name.title()
        if "Singapore" in clean:
            return "Singapore"
        if "Rotterdam" in clean:
            return "Rotterdam"
        if "Fujairah" in clean:
            return "Fujairah"
        if "Houston" in clean:
            return "Houston"
        if "Mumbai" in clean:
            return "Mumbai"
        return clean

    @staticmethod
    def _select_benchmark(quotes: List[BunkerFuelPrice], default_date: str) -> BunkerBenchmark:
        """Selects primary benchmark: Singapore VLSFO > Rotterdam VLSFO > any VLSFO > first quote."""
        # Singapore VLSFO
        for q in quotes:
            if q.port_name == "Singapore" and q.fuel_grade == "VLSFO":
                return BunkerBenchmark(
                    port_name=q.port_name,
                    fuel_grade=q.fuel_grade,
                    price_usd_per_mt=q.price_usd_per_mt,
                    reporting_date=q.reporting_date,
                )

        # Rotterdam VLSFO
        for q in quotes:
            if q.port_name == "Rotterdam" and q.fuel_grade == "VLSFO":
                return BunkerBenchmark(
                    port_name=q.port_name,
                    fuel_grade=q.fuel_grade,
                    price_usd_per_mt=q.price_usd_per_mt,
                    reporting_date=q.reporting_date,
                )

        # Any VLSFO
        for q in quotes:
            if q.fuel_grade == "VLSFO":
                return BunkerBenchmark(
                    port_name=q.port_name,
                    fuel_grade=q.fuel_grade,
                    price_usd_per_mt=q.price_usd_per_mt,
                    reporting_date=q.reporting_date,
                )

        # Fallback to first available
        first = quotes[0]
        return BunkerBenchmark(
            port_name=first.port_name,
            fuel_grade=first.fuel_grade,
            price_usd_per_mt=first.price_usd_per_mt,
            reporting_date=first.reporting_date or default_date,
        )


# Global service instance
bunker_service = BunkerService()
