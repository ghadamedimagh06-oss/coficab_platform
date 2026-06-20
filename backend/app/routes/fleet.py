"""Fleet endpoints: camions, chauffeurs, clients."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db, get_db_optional
from app.models.camion import Camion, CamionStatus
from app.models.chauffeur import Chauffeur, ChauffeurStatus
from app.models.client import Client
from app.services.auth_service import require_role

router = APIRouter()
clients_router = APIRouter()  # mounted at /api/clients


# ── Trucks ─────────────────────────────────────────────────────────────────

@router.get("/trucks")
def list_trucks(
    status: Optional[str] = None,
    db: Optional[Session] = Depends(get_db_optional),
):
    if not db:  # offline mode — the frontend falls back to its bundled fleet
        return []
    q = db.query(Camion)
    if status:
        try:
            q = q.filter(Camion.status == CamionStatus(status.upper()))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown status: {status}")
    trucks = q.order_by(Camion.plate_number).all()
    return [
        {
            "id": t.id,
            "plate_number": t.plate_number,
            "type": t.type,
            "capacite_kg": float(t.capacite_kg) if t.capacite_kg else None,
            "max_palettes": t.max_palettes,
            "status": t.status,
            "consommation_base_l_100km": float(t.consommation_base_l_100km) if t.consommation_base_l_100km else None,
            "chauffeur_defaut_id": t.chauffeur_defaut_id,
        }
        for t in trucks
    ]


@router.get("/trucks/{truck_id}")
def get_truck(truck_id: int, db: Session = Depends(get_db)):
    t = db.query(Camion).filter(Camion.id == truck_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Truck not found")
    return {
        "id": t.id,
        "plate_number": t.plate_number,
        "type": t.type,
        "capacite_kg": float(t.capacite_kg) if t.capacite_kg else None,
        "max_palettes": t.max_palettes,
        "status": t.status,
        "consommation_base_l_100km": float(t.consommation_base_l_100km) if t.consommation_base_l_100km else None,
        "chauffeur_defaut_id": t.chauffeur_defaut_id,
    }


class TruckStatusUpdate(BaseModel):
    status: str


@router.patch("/trucks/{truck_id}/status")
def update_truck_status(
    truck_id: int,
    body: TruckStatusUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role("planner", "admin")),
):
    t = db.query(Camion).filter(Camion.id == truck_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Truck not found")
    try:
        t.status = CamionStatus(body.status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}")
    db.commit()
    return {"id": t.id, "status": t.status}


@router.get("/utilization")
def fleet_utilization(db: Optional[Session] = Depends(get_db_optional)):
    """Summary counts by status — used by dashboard fleet chart."""
    if not db:
        return {"total": 0, "by_status": {}, "utilization_pct": 0}
    trucks = db.query(Camion).all()
    counts = {}
    for t in trucks:
        key = t.status.value if hasattr(t.status, "value") else str(t.status)
        counts[key] = counts.get(key, 0) + 1
    total = len(trucks)
    return {
        "total": total,
        "by_status": counts,
        "utilization_pct": round(
            counts.get("EN_MISSION", 0) / total * 100 if total else 0, 1
        ),
    }


# ── Drivers ────────────────────────────────────────────────────────────────

@router.get("/drivers")
def list_drivers(
    status: Optional[str] = None,
    db: Optional[Session] = Depends(get_db_optional),
):
    if not db:
        return []
    q = db.query(Chauffeur)
    if status:
        try:
            q = q.filter(Chauffeur.status == ChauffeurStatus(status.upper()))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown status: {status}")
    drivers = q.order_by(Chauffeur.full_name).all()
    return [
        {
            "id": d.id,
            "full_name": d.full_name,
            "phone": d.phone,
            "permis_type": d.permis_type,
            "status": d.status,
            "camion_defaut_id": d.camion_defaut_id,
            "shift_start": str(d.shift_start) if d.shift_start else None,
            "shift_end": str(d.shift_end) if d.shift_end else None,
        }
        for d in drivers
    ]


@router.get("/drivers/{driver_id}")
def get_driver(driver_id: int, db: Session = Depends(get_db)):
    d = db.query(Chauffeur).filter(Chauffeur.id == driver_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Driver not found")
    return {
        "id": d.id,
        "full_name": d.full_name,
        "phone": d.phone,
        "permis_type": d.permis_type,
        "status": d.status,
        "camion_defaut_id": d.camion_defaut_id,
        "shift_start": str(d.shift_start) if d.shift_start else None,
        "shift_end": str(d.shift_end) if d.shift_end else None,
    }


# ── Clients — exposed on both /api/fleet/clients and /api/clients ──────────

@router.get("/clients")
@clients_router.get("")
def list_clients(
    city: Optional[str] = None,
    db: Optional[Session] = Depends(get_db_optional),
):
    if not db:
        return []
    q = db.query(Client)
    if city:
        q = q.filter(Client.city.ilike(f"%{city}%"))
    clients = q.order_by(Client.nom).all()
    return [_client_dict(c) for c in clients]


@router.get("/clients/{client_id}")
@clients_router.get("/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db)):
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return _client_dict(c)


def _client_dict(c: Client) -> dict:
    return {
        "id": c.id,
        "nom": c.nom,
        "address": c.address,
        "city": c.city,
        "country": c.country,
        "email": c.email,
        "numero": c.numero,
        "latitude": float(c.latitude) if c.latitude else None,
        "longitude": float(c.longitude) if c.longitude else None,
        "fenetre_ouverture": str(c.fenetre_ouverture) if c.fenetre_ouverture else None,
        "fenetre_fermeture": str(c.fenetre_fermeture) if c.fenetre_fermeture else None,
        "exigences": c.exigences,
    }
