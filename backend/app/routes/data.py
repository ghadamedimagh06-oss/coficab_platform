"""
Data Routes for CofICab Platform
API endpoints for retrieving livraison and ingestion data
"""

from fastapi import APIRouter, Query, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Optional, List
import os
import datetime
from pathlib import Path
import pandas as pd
from app.database import get_db_optional
from app.models.livraison import Livraison
from app.models.ingestion_log import IngestionLog
from app.services.ingestion_service import IngestionService
from app.services.planning_service import PlanningService
from app.services.auth_service import decode_token
from app.data.synthetic_daily_planning import MOCK_TRANSPORTS

router = APIRouter()

# Resolve the weekly-planning workbook with NO machine-specific paths:
#   1. WEEKLY_PLANNING_FILE_PATH env var (explicit override), else
#   2. the canonical workbook in the repo's "weekly planning/" folder, else
#   3. the most recent *.xlsx in that folder (so a renamed week still works).
# This keeps the backend portable across machines and CI; the previous
# hardcoded "C:\Users\USER\..." default leaked a username and broke elsewhere.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_WEEKLY_DIR = _REPO_ROOT / "weekly planning"


def _resolve_weekly_planning_file() -> Path:
    env_weekly_file = os.getenv("WEEKLY_PLANNING_FILE_PATH")
    if env_weekly_file:
        return Path(env_weekly_file).expanduser().resolve()

    canonical = _WEEKLY_DIR / "Weekly Delivery planning W0526.xlsx"
    if canonical.exists():
        return canonical

    if _WEEKLY_DIR.is_dir():
        candidates = sorted(
            (p for p in _WEEKLY_DIR.glob("*.xlsx") if not p.name.startswith("~$")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]

    # Nothing found — return the canonical path so callers report a clear,
    # non-machine-specific "file not found" against the repo location.
    return canonical


WEEKLY_PLANNING_FILE = _resolve_weekly_planning_file()


def _resolve_delivery_history_file() -> Path:
    env_history_file = os.getenv("DELIVERY_HISTORY_FILE_PATH")
    if env_history_file:
        return Path(env_history_file).expanduser().resolve()

    attached = Path(r"C:\Users\akrem\Downloads\Planning de Livraison 2026 v0.xlsx")
    if attached.exists():
        return attached

    return WEEKLY_PLANNING_FILE


DELIVERY_HISTORY_FILE = _resolve_delivery_history_file()


def _transport_from_row(row):
    return {
        "id": row.get("row_number"),
        "excel_row_index": row.get("excel_row_index"),
        "row_number": row.get("row_number"),
        "delivery_day": row.get("delivery_day"),
        "delivery_date": row.get("delivery_date").isoformat() if row.get("delivery_date") else None,
        "client": row.get("client"),
        "driver": row.get("driver"),
        "vehicle": row.get("vehicle"),
        "etd": row.get("etd"),
        "eta": row.get("eta"),
        "quantity": row.get("quantity"),
        "position_count": row.get("position_count") or row.get("quantity"),
        "pallet_weight_kg": row.get("pallet_weight_kg"),
        "gross_weight_kg": row.get("gross_weight_kg"),
        "total_gross_weight_kg": row.get("total_gross_weight_kg"),
        "start_location": row.get("start_location"),
        "end_location": row.get("end_location"),
        "distance_km": row.get("distance_km"),
        "status": row.get("status") or "pending",
        "priority": row.get("priority") or "normal",
        "notes": row.get("notes"),
        "created_at": None,
    }


def _validate_optional_bearer(authorization: Optional[str]) -> None:
    if not authorization:
        return
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or not decode_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _load_weekly_planning_transports(status: Optional[str] = None, day: Optional[str] = None, limit: int = 100, offset: int = 0):
    meta = {
        "source": "excel",
        "source_file": str(WEEKLY_PLANNING_FILE),
        "file_name": WEEKLY_PLANNING_FILE.name,
        "used_mock": False,
        "error": None,
    }
    if WEEKLY_PLANNING_FILE.exists():
        try:
            service = PlanningService(db=None)
            plan_data = service.parse_weekly_planning(str(WEEKLY_PLANNING_FILE))
            rows = [row for row in plan_data["rows"] if row.get("client")]
            if status:
                rows = [row for row in rows if (row.get("status") or "pending") == status]
            if day:
                rows = [row for row in rows if row.get("delivery_day") == day]
            total = len(rows)
            paginated = rows[offset: offset + limit]
            return [_transport_from_row(row) for row in paginated], total, meta
        except Exception as exc:
            meta["error"] = f"Excel parsing failed: {exc}"
    else:
        meta["error"] = f"Excel file not found: {WEEKLY_PLANNING_FILE}"

    mock = MOCK_TRANSPORTS
    meta["source"] = "mock"
    meta["used_mock"] = True
    if status:
        mock = [t for t in mock if t.get("status") == status]
    if day:
        mock = [t for t in mock if t.get("delivery_day") == day]
    total = len(mock)
    return mock[offset: offset + limit], total, meta


def _history_text(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat"}:
        return None
    return text


def _history_float(value: Any) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _history_date(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    try:
        return pd.to_datetime(value).date().isoformat()
    except Exception:
        return None


def _history_clock(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return f"{int(value.hour):02d}:{int(value.minute):02d}"
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat"}:
        return None
    try:
        parsed = pd.to_datetime(value)
        if not pd.isna(parsed):
            return parsed.strftime("%H:%M")
    except Exception:
        pass
    if ":" in text:
        parts = text.split(":")
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return text


def _clock_minutes(clock: Optional[str]) -> Optional[int]:
    if not clock or ":" not in clock:
        return None
    try:
        hour, minute = clock.split(":")[:2]
        return int(hour) * 60 + int(minute)
    except Exception:
        return None


def _valid_delay_cause(value: Any) -> Optional[str]:
    text = _history_text(value)
    if not text:
        return None
    compact = text.replace(" ", "")
    if compact.isdigit():
        return None
    return text


def _load_delivery_history_rows(limit: int = 5000, offset: int = 0) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    meta = {
        "source": "excel",
        "source_file": str(DELIVERY_HISTORY_FILE),
        "file_name": DELIVERY_HISTORY_FILE.name,
        "sheet_name": "Details local delivery",
        "used_mock": False,
        "error": None,
    }
    if not DELIVERY_HISTORY_FILE.exists():
        meta["source"] = "empty"
        meta["error"] = f"Excel file not found: {DELIVERY_HISTORY_FILE}"
        return [], 0, meta

    try:
        df = pd.read_excel(DELIVERY_HISTORY_FILE, sheet_name="Details local delivery")
    except Exception as exc:
        meta["source"] = "empty"
        meta["error"] = f"Delivery history parsing failed: {exc}"
        return [], 0, meta

    cols = list(df.columns)

    def cell(row, index: int) -> Any:
        return row.iloc[index] if index < len(row) else None

    rows: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        delivery_date = _history_date(cell(row, 2))
        voyage = _history_text(cell(row, 1)) or _history_text(cell(row, 6))
        client = _history_text(cell(row, 7))
        if not any([delivery_date, voyage, client]):
            continue

        target_eta = _history_clock(cell(row, 17))
        real_eta = _history_clock(cell(row, 18))
        target_minutes = _clock_minutes(target_eta)
        real_minutes = _clock_minutes(real_eta)
        delay_minutes = None
        if target_minutes is not None and real_minutes is not None:
            if real_minutes < target_minutes - 720:
                real_minutes += 24 * 60
            delay_minutes = max(0, real_minutes - target_minutes)

        otd = _history_float(cell(row, 22))
        new_otd = _history_float(cell(row, 28))
        cause = _valid_delay_cause(cell(row, 27))
        is_late = bool(cause) or (otd is not None and otd < 0.999) or (new_otd is not None and new_otd < 0.999)

        rows.append({
            "id": int(index) + 2,
            "voyage": voyage,
            "delivery_date": delivery_date,
            "month": _history_text(cell(row, 3)),
            "truck": _history_text(cell(row, 4)) or _history_text(cell(row, 8)) or _history_text(cell(row, 13)),
            "driver": _history_text(cell(row, 5)) or _history_text(cell(row, 14)),
            "client": client,
            "max_truck_weight": _history_float(cell(row, 9)),
            "weight": _history_float(cell(row, 10)),
            "max_positions": _history_float(cell(row, 11)),
            "positions": _history_float(cell(row, 12)),
            "planned_etd": _history_clock(cell(row, 15)),
            "real_etd": _history_clock(cell(row, 16)),
            "target_eta_customer": target_eta,
            "real_eta_customer": real_eta,
            "real_etd_customer": _history_clock(cell(row, 19)),
            "eta_coficab": _history_clock(cell(row, 20)),
            "real_eta_coficab": _history_clock(cell(row, 21)),
            "otd": otd,
            "new_otd": new_otd,
            "km": _history_float(cell(row, 23)),
            "stationnement": _history_clock(cell(row, 24)),
            "trajet_aller": _history_clock(cell(row, 25)),
            "trajet_retour": _history_clock(cell(row, 26)),
            "delay_cause": cause,
            "is_late": is_late,
            "delay_minutes": delay_minutes,
        })

    rows.sort(key=lambda item: (item.get("delivery_date") or "", item.get("voyage") or ""), reverse=True)
    total = len(rows)
    return rows[offset: offset + limit], total, meta


def _delivery_history_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    late = sum(1 for row in rows if row.get("is_late"))
    positions = sum(float(row.get("positions") or 0) for row in rows)
    weight = sum(float(row.get("weight") or 0) for row in rows)
    return {
        "shipments": total,
        "late": late,
        "on_time": max(0, total - late),
        "otd_rate": round((total - late) / total * 100, 1) if total else 0,
        "positions": round(positions, 1),
        "weight_kg": round(weight, 1),
    }


def _delivery_cause_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        if not row.get("is_late"):
            continue
        cause = row.get("delay_cause") or "Cause non renseignée"
        counts[cause] = counts.get(cause, 0) + 1
    return [
        {"cause": cause, "count": count}
        for cause, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]

@router.get("/transports")
async def get_transports(
    status: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    force_file: Optional[bool] = Query(False),
    authorization: Optional[str] = Header(None),
    db: Optional[Session] = Depends(get_db_optional)
):
    """Retrieve all livraisons/transports - public endpoint"""
    _validate_optional_bearer(authorization)
    try:
        # If `force_file` requested, return parsed Excel/mock data regardless of DB
        if force_file:
            transports, total, meta = _load_weekly_planning_transports(status=status, day=day, limit=limit, offset=offset)
            return {"transports": transports, "total": total, **meta}

        # If database is available, fetch real data
        if db:
            query = db.query(Livraison)

            # Apply filters if provided
            if status:
                query = query.filter(Livraison.status == status)
            if day:
                query = query.filter(Livraison.delivery_day == day)

            # Get total count
            total = query.count()

            # Apply pagination
            livraisons = query.offset(offset).limit(limit).all()

            # Convert to response format
            transport_list = []
            for livraison in livraisons:
                transport_list.append({
                    "id": livraison.id,
                    "row_number": livraison.row_number,
                    "delivery_day": livraison.delivery_day,
                    "delivery_date": livraison.delivery_date.isoformat() if livraison.delivery_date else None,
                    "client": livraison.client,
                    "driver": livraison.driver,
                    "vehicle": livraison.vehicle,
                    "etd": livraison.etd,
                    "eta": livraison.eta,
                    "quantity": livraison.quantity,
                    "position_count": livraison.quantity,
                    "pallet_weight_kg": None,
                    "gross_weight_kg": None,
                    "total_gross_weight_kg": None,
                    "start_location": livraison.start_location,
                    "end_location": livraison.end_location,
                    "distance_km": livraison.distance_km,
                    "status": livraison.status,
                    "priority": livraison.priority,
                    "notes": livraison.notes,
                    "created_at": livraison.created_at.isoformat() if livraison.created_at else None
                })

            return {
                "transports": transport_list,
                "total": total,
                "source": "database",
                "used_mock": False,
            }
        else:
            transports, total, meta = _load_weekly_planning_transports(status=status, day=day, limit=limit, offset=offset)
            return {"transports": transports, "total": total, **meta}

    except Exception as e:
        # Return file-based or mock data on error
        transports, total, meta = _load_weekly_planning_transports(status=status, day=day, limit=limit, offset=offset)
        return {
            "transports": transports,
            "total": total,
            **meta,
            "error": meta.get("error") or f"Database error: {str(e)}"
        }


@router.get("/delivery-history")
async def get_delivery_history(
    limit: int = Query(5000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(None),
):
    """Return delivery execution history parsed from the 2026 workbook."""
    _validate_optional_bearer(authorization)
    rows, total, meta = _load_delivery_history_rows(limit=limit, offset=offset)
    return {
        "rows": rows,
        "total": total,
        "summary": _delivery_history_summary(rows),
        "cause_stats": _delivery_cause_stats(rows),
        **meta,
    }


@router.get("/source-status")
async def get_source_status(db: Optional[Session] = Depends(get_db_optional)):
    """Report where the platform is currently sourcing operational data from.

    The frontend uses this to show a persistent "DEMO DATA" banner whenever the
    app is serving mock/file data instead of the live database, so fabricated
    numbers can never be mistaken for real ones.
    """
    db_connected = False
    db_has_data = False
    if db is not None:
        try:
            db_has_data = db.query(Livraison).limit(1).count() > 0
            db_connected = True
        except Exception:
            db_connected = False

    file_exists = WEEKLY_PLANNING_FILE.exists()

    if db_connected and db_has_data:
        source = "database"
    elif file_exists:
        source = "excel"
    else:
        source = "mock"

    return {
        "source": source,
        "used_mock": source == "mock",
        "is_live": source == "database",
        "db_connected": db_connected,
        "db_has_data": db_has_data,
        "file_exists": file_exists,
        "file_name": WEEKLY_PLANNING_FILE.name if file_exists else None,
    }


@router.get("/ingestion-history")
async def get_ingestion_history(
    limit: int = Query(50),
    db: Optional[Session] = Depends(get_db_optional)
):
    """Get ingestion processing history"""
    try:
        if db:
            ingestion_service = IngestionService(db)
            history = ingestion_service.get_ingestion_history(limit)
            return {"history": history}
        else:
            return {
                "history": [
                    {
                        "id": 1,
                        "file_name": "weekly_planning.xlsx",
                        "import_date": "2026-05-06T10:00:00",
                        "status": "success",
                        "inserted_rows": 25,
                        "total_rows": 25,
                        "error_message": None
                    }
                ]
            }
    except Exception as e:
        return {
            "history": [],
            "error": f"Failed to retrieve history: {str(e)}"
        }

@router.get("/stats")
async def get_data_stats(db: Optional[Session] = Depends(get_db_optional)):
    """Get data statistics"""
    try:
        if db:
            # Count livraisons by status
            status_counts = {}
            for status in ["pending", "in_transit", "completed"]:
                count = db.query(Livraison).filter(Livraison.status == status).count()
                status_counts[status] = count

            # Total livraisons
            total_livraisons = db.query(Livraison).count()

            # Recent imports
            recent_imports = db.query(IngestionLog).filter(
                IngestionLog.status == "success"
            ).order_by(IngestionLog.import_date.desc()).limit(5).all()

            return {
                "total_livraisons": total_livraisons,
                "status_breakdown": status_counts,
                "recent_imports": len(recent_imports),
                "last_import": recent_imports[0].import_date.isoformat() if recent_imports else None
            }
        else:
            return {
                "total_livraisons": 2,
                "status_breakdown": {"pending": 0, "in_transit": 1, "completed": 1},
                "recent_imports": 1,
                "last_import": "2026-05-06T10:00:00"
            }
    except Exception as e:
        return {
            "total_livraisons": 0,
            "status_breakdown": {"pending": 0, "in_transit": 0, "completed": 0},
            "recent_imports": 0,
            "error": f"Failed to get stats: {str(e)}"
        }
