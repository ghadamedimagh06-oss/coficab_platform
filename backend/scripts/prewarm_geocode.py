"""Offline geocode-cache warmer for the daily planner.

Reads the authoritative client directory (app/data/clients_directory.json),
resolves + geocodes every entry once through GeoService (which honours the
Nominatim 1 req/s policy), and persists the result to
app/data/geocode_cache.json. Run this before the first user hits the server so
the geocode-heavy planning routes return from a warm cache instead of blocking
on ~1s-per-lookup network calls.

Usage:
  python backend/scripts/prewarm_geocode.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.geo_service import GeoService, CLIENTS_DIRECTORY, GEOCODE_CACHE  # noqa: E402


def main() -> None:
    try:
        directory = json.loads(CLIENTS_DIRECTORY.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Could not read client directory {CLIENTS_DIRECTORY}: {exc}")
        sys.exit(1)

    geo = GeoService()
    # Warm the depot too — every plan needs it.
    geo.depot()

    warmed = 0
    for entry in directory:
        customer = (entry.get("customer") or "").strip()
        if not customer:
            continue
        located = geo.locate(customer)
        if located and located.get("lat") is not None:
            print(f"  ✓ {customer} -> ({located['lat']:.5f}, {located['lon']:.5f})")
            warmed += 1
        elif located and located.get("is_export"):
            print(f"  · {customer} -> export site (no domestic geocode)")
        else:
            print(f"  ✗ {customer} -> could not resolve")

    print(f"Cache warmed: {warmed} entries -> {GEOCODE_CACHE}")


if __name__ == "__main__":
    main()
