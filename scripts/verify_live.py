"""
scripts/verify_live.py — Live Verification Script for TinyFish Integration.
============================================================================
Checks environment configuration and performs live or mocked verification:
  • Validates presence of TINYFISH_API_KEY
  • Performs minimal single-shot BDI extraction
  • Performs minimal single-shot Bunker Fuel price extraction
  • Verifies persistence and ML adapter execution
  • Reports clear, actionable diagnostic output
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from backend.config import settings
from backend.services.bdi_service import bdi_service
from backend.services.bunker_service import bunker_service
from backend.services.cache_service import cache_service
from backend.services.ml_adapter import ml_adapter


async def main():
    print("=" * 80)
    print("SAIL YANTRA — TINYFISH LIVE INTEGRATION VERIFICATION")
    print("=" * 80)

    print(f"Target Base URL     : {settings.TINYFISH_BASE_URL}")
    print(f"BDI Target URL      : {settings.BDI_SOURCE_URL}")
    print(f"Bunker Target URL   : {settings.BUNKER_SOURCE_URL}")
    print(f"Cache File Path     : {settings.CACHE_FILE_PATH}")

    api_key = settings.TINYFISH_API_KEY
    if not api_key:
        print("\n[INFO] TINYFISH_API_KEY is not set in environment or .env file.")
        print("[INFO] Checking local cache and fallback degradation behavior...")

        bdi_resp = await bdi_service.get_latest_bdi()
        print(f"  ✓ BDI Endpoint Status       : {bdi_resp.status} (Freshness: {bdi_resp.freshness})")
        print(f"  ✓ BDI Value                 : {bdi_resp.data.value} {bdi_resp.data.unit}")

        bunker_resp = await bunker_service.get_latest_bunker_prices()
        print(f"  ✓ Bunker Endpoint Status    : {bunker_resp.status} (Freshness: {bunker_resp.freshness})")
        print(f"  ✓ Bunker Benchmark          : {bunker_resp.data.benchmark.port_name} {bunker_resp.data.benchmark.fuel_grade} @ ${bunker_resp.data.benchmark.price_usd_per_mt}/MT")

        print("\n[RESULT] Live TinyFish API calls are pending valid user credentials.")
        print("To verify against the live TinyFish cloud:")
        print("  1. Create an account at https://tinyfish.ai to obtain your API key.")
        print("  2. Set TINYFISH_API_KEY=<your_key> in .env or your environment.")
        print("  3. Re-run this script: python scripts/verify_live.py")
        return

    masked_key = api_key[:4] + "..." + api_key[-4:]
    print(f"TINYFISH_API_KEY    : Configured ({masked_key})")
    print("\nExecuting live API extraction with TinyFish...")

    # 1. BDI Live Extraction
    print("\n[1/3] Testing Live Baltic Dry Index (BDI) Extraction...")
    try:
        bdi_res = await bdi_service.fetch_live_bdi()
        print(f"  ✓ Live BDI extracted successfully!")
        print(f"    • Value           : {bdi_res.data.value} {bdi_res.data.unit}")
        print(f"    • Daily Change    : {bdi_res.data.daily_change} ({bdi_res.data.daily_change_pct}%)")
        print(f"    • Reporting Date  : {bdi_res.data.reporting_date}")
        print(f"    • Source URL      : {bdi_res.source_url}")
        print(f"    • Extracted At    : {bdi_res.extracted_at}")
    except Exception as e:
        print(f"  ✗ Live BDI extraction failed: {e}")

    # 2. Bunker Fuel Live Extraction
    print("\n[2/3] Testing Live Marine Bunker Fuel Prices Extraction...")
    try:
        bunker_res = await bunker_service.fetch_live_bunker_prices()
        print(f"  ✓ Live Bunker Prices extracted successfully!")
        print(f"    • Benchmark Port  : {bunker_res.data.benchmark.port_name}")
        print(f"    • Benchmark Grade : {bunker_res.data.benchmark.fuel_grade}")
        print(f"    • Benchmark Price : ${bunker_res.data.benchmark.price_usd_per_mt}/MT")
        print(f"    • Total Quotes    : {len(bunker_res.data.ports)}")
        for p in bunker_res.data.ports[:5]:
            print(f"      - {p.port_name} | {p.fuel_grade}: ${p.price_usd_per_mt}/MT ({p.reporting_date})")
    except Exception as e:
        print(f"  ✗ Live Bunker extraction failed: {e}")

    # 3. ML Pipeline Adaptation with Live Intelligence
    print("\n[3/3] Verifying End-to-End ML Optimization with Live Market Inputs...")
    try:
        test_voyage = {
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
        opt_res = await ml_adapter.run_adapted_optimization(test_voyage, use_live_market=True)
        print(f"  ✓ ML Optimization completed with live market inputs!")
        print(f"    • Decision        : {opt_res['decision_label']}")
        print(f"    • Applied BDI     : {opt_res['market_provenance']['applied_bdi']}")
        print(f"    • Applied Bunker  : ${opt_res['market_provenance']['applied_bunker_usd_mt']}/MT")
        print(f"    • Net Savings     : ${opt_res['net_savings_usd']:,.2f}")
    except Exception as e:
        print(f"  ✗ ML adaptation failed: {e}")

    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
