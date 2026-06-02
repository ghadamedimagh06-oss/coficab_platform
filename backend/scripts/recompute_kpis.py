"""Backfill KPI snapshots for a date range.

Usage:
  python backend/scripts/recompute_kpis.py --from 2026-05-01 --to 2026-05-31
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.kpi_jobs import recompute  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill KPI snapshots")
    parser.add_argument("--from", dest="start", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="End date, YYYY-MM-DD")
    args = parser.parse_args()

    result = recompute(date.fromisoformat(args.start), date.fromisoformat(args.end))
    print(
        "KPI recompute complete: "
        f"{result['daily_rows']} daily rows, {result['monthly_rows']} monthly rows"
    )


if __name__ == "__main__":
    main()
