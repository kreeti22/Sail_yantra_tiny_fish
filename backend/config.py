"""
backend/config.py — Configuration settings for SAIL YANTRA TinyFish Integration.
================================================================================
Reads configuration and secrets safely from environment variables and optional .env file.
Credentials are never logged or exposed to the client.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Helper to load .env without hard dependency on python-dotenv
def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k not in os.environ:
                os.environ[k] = v

_load_env_file(ROOT_DIR / ".env")

class Settings:
    """Application settings loaded from environment variables."""

    # TinyFish API Configuration
    TINYFISH_API_KEY: str = os.getenv("TINYFISH_API_KEY", "").strip()
    TINYFISH_BASE_URL: str = os.getenv("TINYFISH_BASE_URL", "https://agent.tinyfish.ai").rstrip("/")
    
    # Official Source URLs for Public Extraction
    BDI_SOURCE_URL: str = os.getenv(
        "BDI_SOURCE_URL",
        "https://tradingeconomics.com/commodity/baltic"
    )
    BUNKER_SOURCE_URL: str = os.getenv(
        "BUNKER_SOURCE_URL",
        "https://shipandbunker.com/prices"
    )

    # HTTP Client Timeouts & Retries
    REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("TINYFISH_REQUEST_TIMEOUT_SECONDS", "60.0"))
    CONNECT_TIMEOUT_SECONDS: float = float(os.getenv("TINYFISH_CONNECT_TIMEOUT_SECONDS", "10.0"))
    MAX_RETRIES: int = int(os.getenv("TINYFISH_MAX_RETRIES", "3"))
    RETRY_BACKOFF_FACTOR: float = float(os.getenv("TINYFISH_RETRY_BACKOFF_FACTOR", "1.5"))

    # Caching & Persistence Settings
    CACHE_FILE_PATH: Path = DATA_DIR / "market_cache.json"
    CACHE_TTL_SECONDS: int = int(os.getenv("MARKET_CACHE_TTL_SECONDS", "14400"))  # 4 hours
    
    # Manual Sync Security & Protection
    SYNC_SECRET_TOKEN: str = os.getenv("SYNC_SECRET_TOKEN", "")
    SYNC_MIN_INTERVAL_SECONDS: int = int(os.getenv("SYNC_MIN_INTERVAL_SECONDS", "30"))

    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:8501,*").split(",")
        if origin.strip()
    ]

    # Application Metadata
    APP_NAME: str = "SAIL YANTRA Maritime Intelligence Desk"
    APP_VERSION: str = "1.0.0"

settings = Settings()
