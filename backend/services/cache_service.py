"""
backend/services/cache_service.py — Persistence, Caching, and Freshness Management.
===================================================================================
Provides:
  • Atomic file persistence (JSON in data/market_cache.json)
  • Thread-safe and async-safe in-memory caching with asyncio.Lock
  • Freshness lifecycle: 'fresh' (< TTL), 'stale' (>= TTL), 'fallback' (uninitialized)
  • Fallback seed preservation: preserves previous valid data if a new sync fails
  • Concurrency locking: prevents duplicate background sync jobs
  • Debounce protection against rapid manual sync requests
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from backend.config import settings

logger = logging.getLogger("cache_service")
logger.setLevel(logging.INFO)


# ─────────────────────────────────────────────────────────────────────────────
# INDUSTRY SEED DEFAULTS (Aligned with optimizer.py benchmarks)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_BDI_SEED = {
    "index_name": "Baltic Dry Index",
    "value": 1550.0,
    "daily_change": 0.0,
    "daily_change_pct": 0.0,
    "reporting_date": "2026-10-14",
    "unit": "points",
}

DEFAULT_BUNKER_SEED = {
    "benchmark": {
        "port_name": "Singapore",
        "fuel_grade": "VLSFO",
        "price_usd_per_mt": 640.0,
        "reporting_date": "2026-10-14",
    },
    "ports": [
        {
            "port_name": "Singapore",
            "fuel_grade": "VLSFO",
            "price_usd_per_mt": 640.0,
            "daily_change": -2.5,
            "currency": "USD",
            "unit": "USD/MT",
            "reporting_date": "2026-10-14",
        },
        {
            "port_name": "Singapore",
            "fuel_grade": "HSFO",
            "price_usd_per_mt": 495.0,
            "daily_change": 1.0,
            "currency": "USD",
            "unit": "USD/MT",
            "reporting_date": "2026-10-14",
        },
        {
            "port_name": "Singapore",
            "fuel_grade": "MGO",
            "price_usd_per_mt": 820.0,
            "daily_change": -4.0,
            "currency": "USD",
            "unit": "USD/MT",
            "reporting_date": "2026-10-14",
        },
        {
            "port_name": "Rotterdam",
            "fuel_grade": "VLSFO",
            "price_usd_per_mt": 612.0,
            "daily_change": -1.5,
            "currency": "USD",
            "unit": "USD/MT",
            "reporting_date": "2026-10-14",
        },
        {
            "port_name": "Rotterdam",
            "fuel_grade": "HSFO",
            "price_usd_per_mt": 480.0,
            "daily_change": 0.5,
            "currency": "USD",
            "unit": "USD/MT",
            "reporting_date": "2026-10-14",
        },
        {
            "port_name": "Rotterdam",
            "fuel_grade": "MGO",
            "price_usd_per_mt": 795.0,
            "daily_change": -3.0,
            "currency": "USD",
            "unit": "USD/MT",
            "reporting_date": "2026-10-14",
        },
    ],
}


class MarketCacheService:
    """Manages persistent caching for market intelligence data."""

    def __init__(self, file_path: Optional[Path] = None, ttl_seconds: Optional[int] = None) -> None:
        self.file_path = file_path or settings.CACHE_FILE_PATH
        self.ttl_seconds = ttl_seconds or settings.CACHE_TTL_SECONDS
        self._lock = asyncio.Lock()
        self._sync_lock = asyncio.Lock()
        self._memory_cache: Dict[str, Any] = self._load_from_disk()

    def _load_from_disk(self) -> Dict[str, Any]:
        """Loads cache from JSON file, or initializes empty structure."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info("Loaded market cache from %s", self.file_path)
                    return data
            except Exception as e:
                logger.warning("Could not read cache file %s (%s). Starting clean.", self.file_path, e)

        return {
            "bdi": None,
            "bunker": None,
            "sync": {
                "last_sync_attempt": None,
                "last_successful_sync": None,
                "in_progress": False,
                "last_error": None,
            },
        }

    def _persist_to_disk_sync(self) -> None:
        """Atomic write to disk using temp file."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.file_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._memory_cache, f, indent=2)
            tmp_path.replace(self.file_path)
        except Exception as e:
            logger.error("Failed to persist market cache to %s: %s", self.file_path, e)

    def _compute_freshness(self, extracted_at_str: Optional[str]) -> str:
        """Determines if cached data is 'fresh' or 'stale' based on TTL."""
        if not extracted_at_str:
            return "fallback"
        try:
            extracted_at = datetime.datetime.fromisoformat(extracted_at_str)
            now = datetime.datetime.now(datetime.timezone.utc)
            if extracted_at.tzinfo is None:
                extracted_at = extracted_at.replace(tzinfo=datetime.timezone.utc)
            age = (now - extracted_at).total_seconds()
            return "fresh" if age < self.ttl_seconds else "stale"
        except Exception:
            return "stale"

    # ─────────────────────────────────────────────────────────────────────────
    # BDI CACHE
    # ─────────────────────────────────────────────────────────────────────────
    async def get_bdi(self) -> Tuple[Dict[str, Any], str, Optional[str], str]:
        """
        Retrieves BDI data, freshness status, extracted timestamp, and source URL.
        Returns: (data_dict, freshness, extracted_at, source_url)
        """
        async with self._lock:
            entry = self._memory_cache.get("bdi")
            if entry and entry.get("data"):
                freshness = self._compute_freshness(entry.get("extracted_at"))
                return (
                    entry["data"],
                    freshness,
                    entry.get("extracted_at"),
                    entry.get("source_url", settings.BDI_SOURCE_URL),
                )

            # Fallback seed
            return (
                DEFAULT_BDI_SEED,
                "fallback",
                None,
                settings.BDI_SOURCE_URL,
            )

    async def save_bdi(
        self,
        data: Dict[str, Any],
        source_url: str,
        extracted_at: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Saves successful BDI extraction and flushes to disk."""
        async with self._lock:
            if not extracted_at:
                extracted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._memory_cache["bdi"] = {
                "data": data,
                "source_url": source_url,
                "extracted_at": extracted_at,
                "status": "success" if not error else "degraded",
                "last_error": error,
            }
            self._persist_to_disk_sync()

    async def record_bdi_failure(self, error: str) -> None:
        """Records BDI failure while preserving previous data as stale."""
        async with self._lock:
            entry = self._memory_cache.get("bdi")
            if entry:
                entry["last_error"] = error
                entry["status"] = "stale"
            else:
                self._memory_cache["bdi"] = {
                    "data": DEFAULT_BDI_SEED,
                    "source_url": settings.BDI_SOURCE_URL,
                    "extracted_at": None,
                    "status": "fallback",
                    "last_error": error,
                }
            self._persist_to_disk_sync()

    # ─────────────────────────────────────────────────────────────────────────
    # BUNKER FUEL CACHE
    # ─────────────────────────────────────────────────────────────────────────
    async def get_bunker(self) -> Tuple[Dict[str, Any], str, Optional[str], str]:
        """
        Retrieves bunker data, freshness, timestamp, and source URL.
        Returns: (data_dict, freshness, extracted_at, source_url)
        """
        async with self._lock:
            entry = self._memory_cache.get("bunker")
            if entry and entry.get("data"):
                freshness = self._compute_freshness(entry.get("extracted_at"))
                return (
                    entry["data"],
                    freshness,
                    entry.get("extracted_at"),
                    entry.get("source_url", settings.BUNKER_SOURCE_URL),
                )

            # Fallback seed
            return (
                DEFAULT_BUNKER_SEED,
                "fallback",
                None,
                settings.BUNKER_SOURCE_URL,
            )

    async def save_bunker(
        self,
        data: Dict[str, Any],
        source_url: str,
        extracted_at: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Saves successful bunker prices extraction and flushes to disk."""
        async with self._lock:
            if not extracted_at:
                extracted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._memory_cache["bunker"] = {
                "data": data,
                "source_url": source_url,
                "extracted_at": extracted_at,
                "status": "success" if not error else "degraded",
                "last_error": error,
            }
            self._persist_to_disk_sync()

    async def record_bunker_failure(self, error: str) -> None:
        """Records bunker failure while preserving previous data."""
        async with self._lock:
            entry = self._memory_cache.get("bunker")
            if entry:
                entry["last_error"] = error
                entry["status"] = "stale"
            else:
                self._memory_cache["bunker"] = {
                    "data": DEFAULT_BUNKER_SEED,
                    "source_url": settings.BUNKER_SOURCE_URL,
                    "extracted_at": None,
                    "status": "fallback",
                    "last_error": error,
                }
            self._persist_to_disk_sync()

    # ─────────────────────────────────────────────────────────────────────────
    # SYNC METADATA & CONCURRENCY LOCK
    # ─────────────────────────────────────────────────────────────────────────
    @property
    def sync_lock(self) -> asyncio.Lock:
        return self._sync_lock

    async def can_trigger_sync(self, min_interval_seconds: Optional[int] = None) -> Tuple[bool, str]:
        """Checks rate-limit debounce before allowing a manual sync."""
        interval = min_interval_seconds or settings.SYNC_MIN_INTERVAL_SECONDS
        async with self._lock:
            sync_info = self._memory_cache.get("sync", {})
            if sync_info.get("in_progress"):
                return False, "Synchronization job is currently active."

            last_attempt = sync_info.get("last_sync_attempt")
            if last_attempt:
                try:
                    last_time = datetime.datetime.fromisoformat(last_attempt)
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if last_time.tzinfo is None:
                        last_time = last_time.replace(tzinfo=datetime.timezone.utc)
                    elapsed = (now - last_time).total_seconds()
                    if elapsed < interval:
                        return (
                            False,
                            f"Manual sync requested too soon. Please wait {int(interval - elapsed)}s.",
                        )
                except Exception:
                    pass

            return True, "OK"

    async def set_sync_in_progress(self, in_progress: bool, error: Optional[str] = None) -> None:
        """Marks active sync state."""
        async with self._lock:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if "sync" not in self._memory_cache:
                self._memory_cache["sync"] = {}
            
            sync_info = self._memory_cache["sync"]
            sync_info["in_progress"] = in_progress
            if in_progress:
                sync_info["last_sync_attempt"] = now_iso
            else:
                if not error:
                    sync_info["last_successful_sync"] = now_iso
                sync_info["last_error"] = error
            self._persist_to_disk_sync()

    async def get_sync_status(self) -> Dict[str, Any]:
        """Returns comprehensive sync status dictionary."""
        async with self._lock:
            sync_info = self._memory_cache.get("sync", {})
            bdi_entry = self._memory_cache.get("bdi")
            bunker_entry = self._memory_cache.get("bunker")

            return {
                "is_syncing": bool(sync_info.get("in_progress", False)),
                "last_sync_attempt": sync_info.get("last_sync_attempt"),
                "last_successful_sync": sync_info.get("last_successful_sync"),
                "last_error": sync_info.get("last_error"),
                "bdi_freshness": self._compute_freshness(bdi_entry.get("extracted_at") if bdi_entry else None),
                "bdi_last_extracted": bdi_entry.get("extracted_at") if bdi_entry else None,
                "bunker_freshness": self._compute_freshness(bunker_entry.get("extracted_at") if bunker_entry else None),
                "bunker_last_extracted": bunker_entry.get("extracted_at") if bunker_entry else None,
                "cache_file_exists": self.file_path.exists(),
                "api_key_configured": bool(settings.TINYFISH_API_KEY),
            }


# Global singleton instance
cache_service = MarketCacheService()
