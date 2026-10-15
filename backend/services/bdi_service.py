"""
backend/services/bdi_service.py — Baltic Dry Index (BDI) TinyFish Ingestion Service.
====================================================================================
Features:
  • Official TinyFish agent extraction targeting public market sources
  • Natural language goal & schema validation
  • Robust normalization of values, dates, and changes
  • Bounds checking (rejects invalid/malformed data)
  • Persistent caching with graceful degradation to last known valid quote
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict, Optional

from backend.config import settings
from backend.schemas.market import BDIData, BDIResponse
from backend.services.cache_service import cache_service
from backend.services.tinyfish_client import (
    TinyFishClient,
    TinyFishError,
    TinyFishMissingKeyError,
    tinyfish_client,
)

logger = logging.getLogger("bdi_service")
logger.setLevel(logging.INFO)

BDI_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "index_name": {"type": "string", "description": "Index name (Baltic Dry Index)"},
        "value": {"type": "number", "description": "Current numeric index value, e.g. 1550"},
        "daily_change": {"type": "number", "description": "Point change from previous session"},
        "daily_change_pct": {"type": "number", "description": "Percentage change from previous session"},
        "reporting_date": {"type": "string", "description": "Date or timestamp of published quote"},
        "unit": {"type": "string", "description": "Unit (points)"},
    },
    "required": ["value"],
}

BDI_GOAL: str = (
    "Extract the latest Baltic Dry Index (BDI) value, absolute point change, percentage change, "
    "and reporting date from this market page. Ensure the numeric value is parsed accurately. Return JSON."
)


class BDIService:
    """Service for ingesting and validating Baltic Dry Index data."""

    def __init__(self, client: Optional[TinyFishClient] = None) -> None:
        self.client = client or tinyfish_client

    async def get_latest_bdi(self, force_refresh: bool = False) -> BDIResponse:
        """
        Retrieves the latest BDI index. If cached and fresh (and not force_refresh),
        returns cached data. Otherwise triggers a TinyFish extraction.
        """
        cached_data, freshness, extracted_at, source_url = await cache_service.get_bdi()

        if freshness == "fresh" and not force_refresh:
            return BDIResponse(
                status="success",
                freshness="fresh",
                data=BDIData(**cached_data),
                extracted_at=extracted_at,
                source_url=source_url,
                message="Retrieved from fresh market cache.",
            )

        # Attempt TinyFish extraction
        try:
            return await self.fetch_live_bdi()
        except TinyFishMissingKeyError as mke:
            logger.info("TinyFish API key not configured: %s", mke)
            return BDIResponse(
                status="fallback" if freshness == "fallback" else "stale",
                freshness=freshness,
                data=BDIData(**cached_data),
                extracted_at=extracted_at,
                source_url=source_url,
                message="TINYFISH_API_KEY is not configured. Serving cached baseline.",
            )
        except Exception as e:
            logger.warning("BDI live extraction failed: %s. Preserving previous data.", e)
            await cache_service.record_bdi_failure(str(e))
            return BDIResponse(
                status="stale",
                freshness="stale",
                data=BDIData(**cached_data),
                extracted_at=extracted_at,
                source_url=source_url,
                message=f"Live extraction failed ({str(e)}). Preserving last known valid market data.",
            )

    async def fetch_live_bdi(self) -> BDIResponse:
        """Calls TinyFish API directly to extract live BDI quote."""
        url = settings.BDI_SOURCE_URL

        logger.info("Initiating TinyFish BDI extraction from %s", url)
        raw_result = await self.client.run_extraction(
            url=url,
            goal=BDI_GOAL,
            output_schema=BDI_OUTPUT_SCHEMA,
            browser_profile="lite",
        )

        extracted_data = raw_result.get("result", {})
        validated_data = self._validate_and_normalize(extracted_data)

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await cache_service.save_bdi(
            data=validated_data.model_dump(),
            source_url=url,
            extracted_at=now_iso,
        )

        return BDIResponse(
            status="success",
            freshness="fresh",
            data=validated_data,
            extracted_at=now_iso,
            source_url=url,
            message="Live BDI successfully ingested via TinyFish.",
        )

    def _validate_and_normalize(self, raw: Dict[str, Any]) -> BDIData:
        """Validates and normalizes raw agent output into a BDIData schema."""
        if not isinstance(raw, dict):
            raise ValueError(f"BDI extraction returned non-dict payload: {type(raw)}")

        # Extract value
        raw_val = raw.get("value")
        if raw_val is None:
            # Fallback search inside keys
            for k in ("bdi", "index", "close", "price", "baltic_dry_index"):
                if k in raw:
                    raw_val = raw[k]
                    break

        if raw_val is None:
            raise ValueError("BDI numeric value missing from extraction output.")

        try:
            # Clean string if formatted with commas (e.g. "1,845")
            if isinstance(raw_val, str):
                raw_val = float(re.sub(r"[^\d.-]", "", raw_val))
            val = float(raw_val)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid BDI numeric value '{raw_val}': {e}")

        # Bounds validation: BDI historically ranges ~200 to 12,000
        if val <= 50 or val > 30000:
            raise ValueError(f"Extracted BDI value {val} is outside valid market parameters [50, 30000].")

        # Daily changes
        daily_change = self._parse_optional_float(raw.get("daily_change"))
        daily_change_pct = self._parse_optional_float(raw.get("daily_change_pct"))

        # Reporting date
        reporting_date = self._normalize_date(raw.get("reporting_date"))

        return BDIData(
            index_name="Baltic Dry Index",
            value=round(val, 2),
            daily_change=daily_change,
            daily_change_pct=daily_change_pct,
            reporting_date=reporting_date,
            unit="points",
        )

    @staticmethod
    def _parse_optional_float(val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            if isinstance(val, str):
                val = re.sub(r"[^\d.+-]", "", val)
            return round(float(val), 2)
        except Exception:
            return None

    @staticmethod
    def _normalize_date(raw_date: Any) -> str:
        today_str = datetime.date.today().isoformat()
        if not raw_date or not isinstance(raw_date, str):
            return today_str

        raw_str = raw_date.strip()
        # Direct ISO YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_str):
            return raw_str

        # Try common date formats
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                dt = datetime.datetime.strptime(raw_str, fmt)
                return dt.date().isoformat()
            except ValueError:
                pass

        # If date string contains year
        match = re.search(r"(\d{4})", raw_str)
        if match:
            return raw_str[:20]

        return today_str


# Global service instance
bdi_service = BDIService()
