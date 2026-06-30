"""Fleet endpoints: camions, chauffeurs, clients."""
from datetime import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field

from app.database import get_db, get_db_optional
from app.models.camion import Camion, CamionStatus, CamionType
from app.models.chauffeur import Chauffeur, ChauffeurStatus, PermisType
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


class TruckCreate(BaseModel):
    plate_number: str = Field(..., min_length=2, max_length=20)
    type: str = Field("PORTEUR", max_length=30)
    capacite_kg: float = Field(..., gt=0)
    max_palettes: int = Field(..., gt=0)
    status: str = "DISPONIBLE"
    consommation_base_l_100km: Optional[float] = Field(None, ge=0)
    chauffeur_defaut_id: Optional[int] = None


@router.post("/trucks", status_code=201)
def create_truck(
    body: TruckCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    plate_number = body.plate_number.strip().upper()
    if not plate_number:
        raise HTTPException(status_code=422, detail="Plate number cannot be blank")
    if db.query(Camion).filter(Camion.plate_number == plate_number).first() is not None:
        raise HTTPException(status_code=409, detail="Plate number is already assigned")
    try:
        truck_type = CamionType(body.type.upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown truck type: {body.type}") from exc
    try:
        truck_status = CamionStatus(body.status.upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}") from exc

    driver = None
    if body.chauffeur_defaut_id is not None:
        driver = _available_default_driver(db, body.chauffeur_defaut_id)

    truck = Camion(
        plate_number=plate_number,
        type=truck_type,
        capacite_kg=body.capacite_kg,
        max_palettes=body.max_palettes,
        status=truck_status,
        consommation_base_l_100km=body.consommation_base_l_100km,
        chauffeur_defaut_id=body.chauffeur_defaut_id,
    )
    db.add(truck)
    try:
        db.flush()
        if driver is not None:
            driver.camion_defaut_id = truck.id
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Truck assignment conflicts with existing data") from exc
    db.refresh(truck)
    return _truck_dict(truck)


@router.delete("/trucks/{truck_id}")
def delete_truck(
    truck_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    truck = db.get(Camion, truck_id)
    if truck is None:
        raise HTTPException(status_code=404, detail="Truck not found")
    db.query(Chauffeur).filter(Chauffeur.camion_defaut_id == truck_id).update(
        {Chauffeur.camion_defaut_id: None},
        synchronize_session=False,
    )
    db.delete(truck)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Truck is linked to existing planning data") from exc
    return {"status": "deleted", "id": truck_id}


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
    return [_driver_dict(d) for d in drivers]


@router.get("/drivers/{driver_id}")
def get_driver(driver_id: int, db: Session = Depends(get_db)):
    d = db.query(Chauffeur).filter(Chauffeur.id == driver_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Driver not found")
    return _driver_dict(d)


class DriverCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    phone: Optional[str] = Field(None, max_length=30)
    permis_type: PermisType
    permis_numero: Optional[str] = Field(None, max_length=50)
    status: ChauffeurStatus = ChauffeurStatus.ACTIF
    camion_defaut_id: Optional[int] = None
    shift_start: Optional[time] = None
    shift_end: Optional[time] = None


class DriverUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    phone: Optional[str] = Field(None, max_length=30)
    permis_type: Optional[PermisType] = None
    permis_numero: Optional[str] = Field(None, max_length=50)
    status: Optional[ChauffeurStatus] = None
    camion_defaut_id: Optional[int] = None
    shift_start: Optional[time] = None
    shift_end: Optional[time] = None


@router.post("/drivers", status_code=201)
def create_driver(
    body: DriverCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    values = body.model_dump()
    values["full_name"] = values["full_name"].strip()
    if not values["full_name"]:
        raise HTTPException(status_code=422, detail="Full name cannot be blank")
    values["permis_numero"] = _normalize_permit(values.get("permis_numero"))
    _ensure_unique_permit(db, values.get("permis_numero"))
    truck = _available_default_truck(db, values.get("camion_defaut_id"))

    driver = Chauffeur(**values)
    db.add(driver)
    try:
        db.flush()
        if truck is not None:
            truck.chauffeur_defaut_id = driver.id
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Driver assignment conflicts with existing data") from exc
    db.refresh(driver)
    return _driver_dict(driver)


@router.patch("/drivers/{driver_id}")
def update_driver(
    driver_id: int,
    body: DriverUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    driver = db.get(Chauffeur, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    values = body.model_dump(exclude_unset=True)
    if "full_name" in values:
        values["full_name"] = (values["full_name"] or "").strip()
        if not values["full_name"]:
            raise HTTPException(status_code=422, detail="Full name cannot be blank")
    if "permis_numero" in values:
        values["permis_numero"] = _normalize_permit(values["permis_numero"])
        _ensure_unique_permit(db, values["permis_numero"], exclude_driver_id=driver.id)

    new_truck = None
    if "camion_defaut_id" in values:
        new_truck = _available_default_truck(
            db,
            values["camion_defaut_id"],
            exclude_driver_id=driver.id,
        )
        if driver.camion_defaut_id and driver.camion_defaut_id != values["camion_defaut_id"]:
            old_truck = db.get(Camion, driver.camion_defaut_id)
            if old_truck and old_truck.chauffeur_defaut_id == driver.id:
                old_truck.chauffeur_defaut_id = None

    for field, value in values.items():
        setattr(driver, field, value)
    if new_truck is not None:
        new_truck.chauffeur_defaut_id = driver.id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Driver assignment conflicts with existing data") from exc
    db.refresh(driver)
    return _driver_dict(driver)


@router.delete("/drivers/{driver_id}")
def delete_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    driver = db.get(Chauffeur, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    db.query(Camion).filter(Camion.chauffeur_defaut_id == driver_id).update(
        {Camion.chauffeur_defaut_id: None},
        synchronize_session=False,
    )
    db.delete(driver)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Driver is linked to existing planning data") from exc
    return {"status": "deleted", "id": driver_id}


def _truck_dict(truck: Camion) -> dict:
    return {
        "id": truck.id,
        "plate_number": truck.plate_number,
        "type": truck.type,
        "capacite_kg": float(truck.capacite_kg) if truck.capacite_kg else None,
        "max_palettes": truck.max_palettes,
        "status": truck.status,
        "consommation_base_l_100km": (
            float(truck.consommation_base_l_100km) if truck.consommation_base_l_100km else None
        ),
        "chauffeur_defaut_id": truck.chauffeur_defaut_id,
    }


def _driver_dict(driver: Chauffeur) -> dict:
    return {
        "id": driver.id,
        "full_name": driver.full_name,
        "phone": driver.phone,
        "permis_type": driver.permis_type,
        "permis_numero": driver.permis_numero,
        "status": driver.status,
        "camion_defaut_id": driver.camion_defaut_id,
        "shift_start": str(driver.shift_start) if driver.shift_start else None,
        "shift_end": str(driver.shift_end) if driver.shift_end else None,
    }


def _ensure_unique_permit(
    db: Session,
    permit_number: Optional[str],
    exclude_driver_id: Optional[int] = None,
) -> None:
    if not permit_number:
        return
    query = db.query(Chauffeur).filter(Chauffeur.permis_numero == permit_number)
    if exclude_driver_id is not None:
        query = query.filter(Chauffeur.id != exclude_driver_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="Permit number is already assigned")


def _normalize_permit(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().upper()
    return normalized or None


def _available_default_truck(
    db: Session,
    truck_id: Optional[int],
    exclude_driver_id: Optional[int] = None,
) -> Optional[Camion]:
    if truck_id is None:
        return None
    truck = db.get(Camion, truck_id)
    if truck is None:
        raise HTTPException(status_code=404, detail="Default truck not found")
    if truck.chauffeur_defaut_id not in {None, exclude_driver_id}:
        raise HTTPException(status_code=409, detail="Default truck is already assigned")
    query = db.query(Chauffeur).filter(Chauffeur.camion_defaut_id == truck_id)
    if exclude_driver_id is not None:
        query = query.filter(Chauffeur.id != exclude_driver_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="Default truck is already assigned")
    return truck


def _available_default_driver(db: Session, driver_id: int) -> Chauffeur:
    driver = db.get(Chauffeur, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Default driver not found")
    if driver.camion_defaut_id is not None:
        raise HTTPException(status_code=409, detail="Default driver is already assigned")
    query = db.query(Camion).filter(Camion.chauffeur_defaut_id == driver_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="Default driver is already assigned")
    return driver


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
