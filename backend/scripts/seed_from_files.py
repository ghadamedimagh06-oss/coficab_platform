#!/usr/bin/env python3
"""
Seed Postgres from the project's existing data files.

Loads the data the app already ships with into the relational schema so the
dashboard/endpoints can read from Postgres instead of rebuilding everything
in-memory each request:

  app/data/clients_directory.json   -> clients
  weekly planning/*.xlsx (newest)   -> demandes_local  (one row per delivery)

Idempotent: clients are upserted by name; the workbook demand is fully
re-seeded each run (rows tagged source_import='weekly_seed' are deleted first),
so running it twice does not create duplicates.

The weekly workbook carries weekday NAMES (Monday..Saturday), not calendar
dates. demandes_local.date_livraison is NOT NULL, so each weekday is anchored to
the matching day of a reference week (default: the week containing --week-of,
which defaults to today). This mirrors how DailyPlanBuilder maps a requested day
onto the workbook by weekday.

Usage:
  python scripts/seed_from_files.py                 # anchor to this week
  python scripts/seed_from_files.py --week-of 2026-06-08
  python scripts/seed_from_files.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

# Allow running as `python scripts/seed_from_files.py` from the backend dir.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, engine, Base  # noqa: E402
from app.models.client import Client  # noqa: E402
from app.models.demande import DemandeLocal, StatutDemande, Priorite  # noqa: E402
from app.models.camion import Camion  # noqa: E402
from app.models.chauffeur import Chauffeur, PermisType, ChauffeurStatus  # noqa: E402
from app.models.kpi import KpiDefinition, KpiFrequence, KpiDirection  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.planning_service import PlanningService  # noqa: E402

PROJECT_ROOT = BACKEND_DIR.parent
CLIENTS_JSON = BACKEND_DIR / "app" / "data" / "clients_directory.json"
WEEKLY_DIR = PROJECT_ROOT / "weekly planning"

SEED_TAG = "weekly_seed"

_WEEKDAY_INDEX = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_PRIORITY_MAP = {
    "urgent": Priorite.URGENTE,
    "urgente": Priorite.URGENTE,
    "high": Priorite.HAUTE,
    "haute": Priorite.HAUTE,
}

# Drivers mirrored from frontend/data/coficabData.js (`drivers`), each keyed to
# its truck by plate number so we can resolve the camion FK from the DB.
_DRIVERS = [
    {"name": "Ala",     "phone": "+216 20 000 001", "permis": "A001", "shift": "Jour", "plate": "2282TU131"},
    {"name": "Bilel",   "phone": "+216 20 000 002", "permis": "A002", "shift": "Jour", "plate": "9524TU238"},
    {"name": "Hbib",    "phone": "+216 20 000 003", "permis": "A003", "shift": "Nuit", "plate": "5735TU217"},
    {"name": "Houssem", "phone": "+216 20 000 004", "permis": "A004", "shift": "Jour", "plate": "4331TU175"},
    {"name": "Karim",   "phone": "+216 20 000 005", "permis": "A005", "shift": "Jour", "plate": "REM107627"},
    {"name": "Mehrez",  "phone": "+216 20 000 006", "permis": "A006", "shift": "Nuit", "plate": "626TU203"},
    {"name": "Ridha",   "phone": "+216 20 000 007", "permis": "A007", "shift": "Jour", "plate": "7797TU218"},
]

_SHIFTS = {"Jour": (time(6, 0), time(18, 0)), "Nuit": (time(18, 0), time(6, 0))}

# Real COFICAB fleet (mirrors database/seed_demo.sql). Seeded so the DB-aware
# optimiser and the execution/ePOD loop have available trucks out of the box.
# (plate, type, capacite_kg, max_palettes, consommation_l_100km)
_CAMIONS = [
    ("2282TU131", "PORTEUR", 10200, 14, 30.0),
    ("9524TU238", "PORTEUR", 10230, 14, 30.0),
    ("5735TU217", "PORTEUR",  9227, 14, 29.0),
    ("4331TU175", "PORTEUR",  9200, 14, 29.0),
    ("REM107627", "SEMI",    24950, 24, 35.0),
    ("626TU203",  "FOURGON",  7650, 14, 24.0),
    ("7797TU218", "PORTEUR",   925,  4, 18.0),
    ("6502TU247", "PORTEUR",  8500, 14, 28.0),
]

# Official Coficab KPI catalog. Thresholds for the 4 dashboard KPIs (OTIF, OTD,
# Load, Fuel) are authoritative — they match dashboard_service._KPI_BANDS. The
# other 4 indicators are defined (code/name/unit/direction) but their colour
# bands are left NULL until the official targets are provided.
# (code, nom, unite, frequence, direction, target, green_min, yellow_min, green_max, yellow_max)
_KPI_DEFS = [
    ("R4-06",    "OTIF",                        "%",       "daily",   "UP",   95.0, 95.0, 85.0, None, None),
    ("R4-02",    "OTD",                         "%",       "daily",   "UP",   95.0, 95.0, 85.0, None, None),
    ("R4",       "Load Efficiency",             "%",       "daily",   "UP",   80.0, 80.0, 65.0, None, None),
    ("R4-13",    "Fuel Efficiency",             "L/T·km",  "daily",   "DOWN", 0.02, None, None, 0.02, 0.03),
    ("R4-02-PF", "Premium Freight Cost",        "Eur",     "monthly", "DOWN", None, None, None, None, None),
    ("R4-03",    "Premium Freight Occurrences", "Nb",      "monthly", "DOWN", None, None, None, None, None),
    ("R5-10",    "Logistics Cost",              "€/T",     "monthly", "DOWN", None, None, None, None, None),
    ("R4-12",    "Customer Incidents",          "Nb",      "monthly", "DOWN", None, None, None, None, None),
]


def _newest_workbook() -> Path:
    files = [p for p in WEEKLY_DIR.glob("*.xlsx") if not p.name.startswith("~$")]
    weekly = [p for p in files if "weekly" in p.name.lower()]
    pool = weekly or files
    if not pool:
        raise FileNotFoundError(f"no weekly xlsx found in {WEEKLY_DIR}")
    return max(pool, key=lambda p: p.stat().st_mtime)


def _monday_of(ref: date) -> date:
    return ref - timedelta(days=ref.weekday())


def _parse_etd(value, on_day: date):
    """Combine an 'HH:MM' workbook ETD with the delivery date -> datetime."""
    if not value:
        return None
    try:
        h, m = str(value).split(":")[:2]
        return datetime.combine(on_day, time(int(h), int(m)))
    except (ValueError, TypeError):
        return None


# clients.id is a manual business code (no auto-increment sequence in the
# schema), so the seeder assigns ids itself, continuing past whatever exists.
_next_client_id = {"value": 1}


def _alloc_client_id(db) -> int:
    from sqlalchemy import func
    if _next_client_id["value"] == 1:
        current_max = db.query(func.max(Client.id)).scalar()
        _next_client_id["value"] = (int(current_max) + 1) if current_max else 1
    cid = _next_client_id["value"]
    _next_client_id["value"] += 1
    return cid


def seed_clients(db, dry_run: bool) -> dict[str, int]:
    """Upsert clients from the directory JSON. Returns name(lower) -> client.id."""
    directory = json.loads(CLIENTS_JSON.read_text(encoding="utf-8"))
    existing = {c.nom.strip().lower(): c for c in db.query(Client).all()}
    name_to_id: dict[str, int] = {}
    created = updated = 0

    for entry in directory:
        name = (entry.get("customer") or "").strip()
        if not name:
            continue
        key = name.lower()
        client = existing.get(key)
        lat = entry.get("lat")
        lon = entry.get("lon")
        km = entry.get("km")
        exigences = f"{km} km from depot" if km is not None else None
        if client is None:
            client = Client(
                id=_alloc_client_id(db),
                nom=name,
                city=entry.get("destination") or None,
                country="Tunisia",
                latitude=lat,
                longitude=lon,
                exigences=exigences,
            )
            db.add(client)
            existing[key] = client
            created += 1
        else:
            client.city = entry.get("destination") or client.city
            client.latitude = lat if lat is not None else client.latitude
            client.longitude = lon if lon is not None else client.longitude
            client.exigences = exigences or client.exigences
            updated += 1

    if not dry_run:
        db.flush()  # assign ids
    for key, client in existing.items():
        name_to_id[key] = client.id
    print(f"  clients: +{created} new, ~{updated} updated ({len(existing)} total)")
    return name_to_id


def _get_or_create_client(db, name: str, name_to_id: dict[str, int]) -> int:
    key = name.strip().lower()
    if key in name_to_id and name_to_id[key] is not None:
        return name_to_id[key]
    client = Client(id=_alloc_client_id(db), nom=name.strip(), country="Tunisia")
    db.add(client)
    db.flush()
    name_to_id[key] = client.id
    return client.id


def seed_demandes(db, name_to_id: dict[str, int], week_monday: date, dry_run: bool) -> None:
    src = _newest_workbook()
    rows = PlanningService(db=None).parse_weekly_planning(str(src))["rows"]

    # Idempotent: drop any previous seed of the weekly demand.
    deleted = (
        db.query(DemandeLocal)
        .filter(DemandeLocal.source_import == SEED_TAG)
        .delete(synchronize_session=False)
    )

    inserted = 0
    skipped = 0
    per_day: dict[str, int] = {}
    for row in rows:
        client_name = (row.get("client") or "").strip()
        if not client_name:
            skipped += 1
            continue
        day_name = (row.get("delivery_day") or "").strip().lower()
        offset = _WEEKDAY_INDEX.get(day_name)
        if offset is None:
            # fall back to a concrete delivery_date if the workbook has one
            d = row.get("delivery_date")
            if d is None:
                skipped += 1
                continue
            dliv = d.date() if hasattr(d, "date") else d
        else:
            dliv = week_monday + timedelta(days=offset)

        client_id = _get_or_create_client(db, client_name, name_to_id)
        positions = row.get("position_count") or row.get("quantity") or 0
        gross = row.get("gross_weight_kg") or row.get("total_gross_weight_kg") or 0.0
        prio = _PRIORITY_MAP.get(str(row.get("priority") or "").strip().lower(), Priorite.NORMALE)

        demande = DemandeLocal(
            client_id=client_id,
            quantite_kg=round(float(gross or 0.0), 2),
            nombre_palettes=int(positions) if positions else None,
            date_livraison=dliv,
            heure_arrivee_prevue=_parse_etd(row.get("etd"), dliv),
            priorite=prio,
            statut=StatutDemande.NOUVELLE,
            commentaire=(row.get("notes") or None),
            source_import=SEED_TAG,
        )
        db.add(demande)
        inserted += 1
        per_day[dliv.isoformat()] = per_day.get(dliv.isoformat(), 0) + 1

    print(f"  demandes_local: -{deleted} old seed, +{inserted} inserted, {skipped} skipped")
    print(f"    source: {src.name}")
    for d in sorted(per_day):
        print(f"    {d}: {per_day[d]} deliveries")


def seed_camions(db, dry_run: bool) -> None:
    """Upsert the real COFICAB fleet by plate number (status DISPONIBLE)."""
    from app.models.camion import CamionType, CamionStatus
    existing = {c.plate_number.strip().lower(): c for c in db.query(Camion).all()}
    created = updated = 0
    for plate, ctype, cap_kg, max_pal, conso in _CAMIONS:
        key = plate.strip().lower()
        cam = existing.get(key)
        fields = dict(
            type=CamionType(ctype),
            capacite_kg=cap_kg,
            max_palettes=max_pal,
            consommation_base_l_100km=conso,
        )
        if cam is None:
            db.add(Camion(plate_number=plate, status=CamionStatus.DISPONIBLE, **fields))
            created += 1
        else:
            for k, v in fields.items():
                setattr(cam, k, v)
            updated += 1
    db.flush()
    print(f"  camions: +{created} new, ~{updated} updated ({len(_CAMIONS)} total)")


def seed_chauffeurs(db, dry_run: bool) -> None:
    """Upsert drivers (from coficadData), linking each to its default camion."""
    camions_by_plate = {
        c.plate_number.strip().lower(): c.id for c in db.query(Camion).all()
    }
    existing = {ch.full_name.strip().lower(): ch for ch in db.query(Chauffeur).all()}
    created = updated = 0
    for d in _DRIVERS:
        key = d["name"].strip().lower()
        camion_id = camions_by_plate.get(d["plate"].strip().lower())
        s_start, s_end = _SHIFTS.get(d["shift"], (None, None))
        ch = existing.get(key)
        if ch is None:
            db.add(Chauffeur(
                full_name=d["name"],
                phone=d["phone"],
                permis_type=PermisType.C,
                permis_numero=d["permis"],
                status=ChauffeurStatus.ACTIF,
                camion_defaut_id=camion_id,
                shift_start=s_start,
                shift_end=s_end,
            ))
            created += 1
        else:
            ch.phone = d["phone"]
            ch.permis_numero = d["permis"]
            ch.camion_defaut_id = camion_id
            ch.shift_start, ch.shift_end = s_start, s_end
            updated += 1
    print(f"  chauffeurs: +{created} new, ~{updated} updated")


def _bcrypt_hash(password: str) -> str:
    """Produce a standard $2b$ bcrypt hash, matching auth_service.hash_password."""
    from app.services.auth_service import hash_password
    return hash_password(password)


def seed_admin_user(db, dry_run: bool) -> None:
    """Create the default admin login if it does not exist yet."""
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        if existing.role != "admin":
            existing.role = "admin"
        print("  users: admin already exists")
        return
    if dry_run:
        print("  users: would create admin (dry-run)")
        return
    db.add(User(
        username="admin",
        email="admin@coficab.local",
        password_hash=_bcrypt_hash("admin123"),
        role="admin",
        is_active=True,
    ))
    print("  users: +1 admin created (admin / admin123)")


def seed_kpi_definitions(db, dry_run: bool) -> None:
    """Upsert the official KPI catalog by code."""
    existing = {k.code: k for k in db.query(KpiDefinition).all()}
    created = updated = 0
    for code, nom, unite, freq, direction, target, gmin, ymin, gmax, ymax in _KPI_DEFS:
        kd = existing.get(code)
        fields = dict(
            nom=nom, unite=unite,
            frequence=KpiFrequence(freq), direction=KpiDirection(direction),
            target_2025=target, green_min=gmin, yellow_min=ymin,
            green_max=gmax, yellow_max=ymax,
        )
        if kd is None:
            db.add(KpiDefinition(code=code, **fields))
            created += 1
        else:
            for k, v in fields.items():
                setattr(kd, k, v)
            updated += 1
    print(f"  kpi_definition: +{created} new, ~{updated} updated ({len(_KPI_DEFS)} total)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed Postgres from project data files")
    ap.add_argument("--week-of", type=str, default=None,
                    help="anchor weekday names to the week containing this YYYY-MM-DD (default: today)")
    ap.add_argument("--dry-run", action="store_true", help="roll back instead of committing")
    args = ap.parse_args()

    if not SessionLocal:
        print("ERROR: database not available — check DATABASE_URL / Postgres is running")
        sys.exit(1)

    ref = date.fromisoformat(args.week_of) if args.week_of else date.today()
    week_monday = _monday_of(ref)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print(f"Seeding Postgres (week of {week_monday.isoformat()})"
              + (" [DRY-RUN]" if args.dry_run else ""))
        name_to_id = seed_clients(db, args.dry_run)
        seed_demandes(db, name_to_id, week_monday, args.dry_run)
        seed_camions(db, args.dry_run)
        seed_chauffeurs(db, args.dry_run)
        seed_admin_user(db, args.dry_run)
        seed_kpi_definitions(db, args.dry_run)
        if args.dry_run:
            db.rollback()
            print("DRY-RUN: rolled back, nothing committed.")
        else:
            db.commit()
            print("Committed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
