"""
KPI computation service — implements all 8 Coficab indicators (skill 01).

Priority order:
  1. Read pre-computed rows from kpi_journalier / kpi_mensuel (fast, for dashboards).
  2. If no rows exist, compute on-the-fly from plan_mission / demandes_local / evenement_alea.
  3. Compute color band from kpi_definition thresholds.

All formulas match the spec in skill 01 verbatim.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.kpi import KpiDefinition, KpiJournalier, KpiMensuel, KpiStatus

log = logging.getLogger(__name__)

# KPI catalog ordered as dashboard expects
KPI_CODES_ORDERED = ["R4-06", "R4-02", "R4-02-PF", "R4-03", "R4-13", "R5-10", "R4-12", "R4"]

FRIENDLY_LABELS = {
    "R4-06":   "OTIF",
    "R4-02":   "OTD",
    "R4-02-PF":"Premium Freight Cost",
    "R4-03":   "Premium Freight Occurrences",
    "R4-13":   "Fuel Efficiency",
    "R5-10":   "Logistics Cost",
    "R4-12":   "Customer Incidents",
    "R4":      "Load Efficiency",
}


# Presentation metadata for the dashboard KPI cards. Kept here (not in the DB)
# so the cards still render their names/units/icons offline. Icon names must
# exist in the frontend iconMap.
DASHBOARD_KPI_META = {
    "R4-06":    {"id": "otif",          "icon": "truck",         "unit": "%",       "hint": "delivered on-time & in-full ÷ delivered"},
    "R4-02":    {"id": "otd",           "icon": "clock",         "unit": "%",       "hint": "delivered on time ÷ delivered"},
    "R4-02-PF": {"id": "premium_cost",  "icon": "bar-chart-3",   "unit": "Eur",     "hint": "extra / premium transport cost"},
    "R4-03":    {"id": "premium_occ",   "icon": "alert-triangle","unit": "Nb",      "hint": "premium freight occurrences"},
    "R4-13":    {"id": "fuel",          "icon": "gauge",         "unit": "mL/T.km", "hint": "fuel per tonne-kilometre"},
    "R5-10":    {"id": "logistics_cost","icon": "bar-chart-3",   "unit": "€/T",     "hint": "logistics cost per tonne"},
    "R4-12":    {"id": "incidents",     "icon": "alert-triangle","unit": "Nb",      "hint": "customer incidents per MKm sold"},
    "R4":       {"id": "load",          "icon": "gauge",         "unit": "%",       "hint": "max(pallet, weight) fill"},
}


def dashboard_kpi_cards(db: Optional[Session], start: date, end: date) -> list[dict]:
    """The official Coficab KPI cards over [start, end] for the dashboard.

    With a DB session → real values from the live computers (delivery actuals);
    offline (db is None) → the same cards greyed out with a 'needs delivery
    data' hint, so the dashboard never shows fabricated KPI numbers.
    """
    defs: dict[str, KpiDefinition] = {}
    svc: Optional["KpiService"] = None
    if db is not None:
        try:
            svc = KpiService(db)
            defs = {d.code: d for d in db.query(KpiDefinition).all()}
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("KPI definitions unavailable: %s", exc)
            svc = None

    cards: list[dict] = []
    for code in KPI_CODES_ORDERED:
        meta = DASHBOARD_KPI_META.get(code, {"id": code, "icon": "bar-chart-3", "unit": "", "hint": ""})
        kd = defs.get(code)
        value = svc._compute_live(code, start, end) if svc is not None else None
        color = compute_color(kd, value) if (kd is not None and value is not None) else "grey"
        cards.append({
            "code": code,
            "id": meta["id"],
            "label": FRIENDLY_LABELS.get(code, code),
            "value": round(value, 4) if value is not None else None,
            "unit": (kd.unite if (kd and kd.unite) else meta["unit"]),
            "target": float(kd.target_2025) if (kd and kd.target_2025 is not None) else None,
            "color": color,
            "icon": meta["icon"],
            "hint": meta["hint"] if value is not None else f"{meta['hint']} · needs delivery data",
        })
    return cards


def compute_color(kpi_def: KpiDefinition, value: float) -> str:
    if value is None:
        return "grey"
    direction = kpi_def.direction.value if hasattr(kpi_def.direction, "value") else kpi_def.direction
    if direction == "UP":
        green_min = float(kpi_def.green_min) if kpi_def.green_min is not None else None
        yellow_min = float(kpi_def.yellow_min) if kpi_def.yellow_min is not None else None
        if green_min is not None and value >= green_min:
            return "green"
        if yellow_min is not None and value >= yellow_min:
            return "yellow"
        return "red"
    else:  # DOWN
        green_max = float(kpi_def.green_max) if kpi_def.green_max is not None else None
        yellow_max = float(kpi_def.yellow_max) if kpi_def.yellow_max is not None else None
        if green_max is not None and value <= green_max:
            return "green"
        if yellow_max is not None and value <= yellow_max:
            return "yellow"
        return "red"


class KpiService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_dashboard_kpis(self, ref_date: date | None = None) -> list[dict]:
        """
        Return the 8 KPIs formatted for the dashboard.
        Uses last 30 days of data for on-the-fly computation.
        """
        if ref_date is None:
            ref_date = date.today()

        defs = {
            d.code: d
            for d in self.db.query(KpiDefinition).all()
        }
        if not defs:
            return self._empty_kpis()

        results = []
        for code in KPI_CODES_ORDERED:
            kd = defs.get(code)
            if not kd:
                continue
            value, prev_value = self._get_value(code, ref_date)
            color = compute_color(kd, value) if value is not None else "grey"
            trend = self._trend(value, prev_value)
            results.append({
                "code": code,
                "label": FRIENDLY_LABELS.get(code, kd.nom),
                "value": round(value, 4) if value is not None else None,
                "unit": kd.unite,
                "color": color,
                "target": float(kd.target_2025) if kd.target_2025 is not None else None,
                "trend": trend,
            })
        return results

    def get_weekly_delivery_trend(self, weeks: int = 8) -> list[dict]:
        """Weekly aggregates: total demandes, delivered, on-time."""
        from app.models.demande import DemandeLocal, StatutDemande
        today = date.today()
        rows = []
        for w in range(weeks - 1, -1, -1):
            start = today - timedelta(days=today.weekday() + 7 * w)
            end = start + timedelta(days=6)
            q = self.db.query(
                func.count(DemandeLocal.id).label("total"),
                func.sum(
                    func.cast(DemandeLocal.statut == StatutDemande.LIVREE, int)
                ).label("delivered"),
                func.sum(
                    func.cast(DemandeLocal.livree_a_temps == True, int)
                ).label("on_time"),
            ).filter(
                DemandeLocal.date_livraison >= start,
                DemandeLocal.date_livraison <= end,
            ).first()
            rows.append({
                "week": start.strftime("W%W"),
                "date": start.isoformat(),
                "total": int(q.total or 0),
                "delivered": int(q.delivered or 0),
                "on_time": int(q.on_time or 0),
            })
        return rows

    def get_efficiency_distribution(self) -> list[dict]:
        """Distribution of load efficiency across missions in the last 30 days."""
        from app.models.plan import PlanMission
        cutoff = date.today() - timedelta(days=30)
        missions = (
            self.db.query(PlanMission.load_eff_pct)
            .filter(PlanMission.date_mission >= cutoff, PlanMission.load_eff_pct.isnot(None))
            .all()
        )
        buckets = {"< 60%": 0, "60-79%": 0, "80-89%": 0, "≥ 90%": 0}
        for (eff,) in missions:
            v = float(eff)
            if v < 60:
                buckets["< 60%"] += 1
            elif v < 80:
                buckets["60-79%"] += 1
            elif v < 90:
                buckets["80-89%"] += 1
            else:
                buckets["≥ 90%"] += 1
        total = sum(buckets.values())
        return [
            {"label": k, "count": v, "pct": round(v / total * 100, 1) if total else 0}
            for k, v in buckets.items()
        ]

    # ------------------------------------------------------------------
    # Value resolution: pre-computed → on-the-fly
    # ------------------------------------------------------------------

    def _get_value(self, code: str, ref_date: date) -> tuple[float | None, float | None]:
        """Return (current_value, prev_month_value). Both may be None."""
        # Try monthly pre-computed first
        current = self._read_monthly(code, ref_date.year, ref_date.month)
        prev_month = date(ref_date.year, ref_date.month, 1) - timedelta(days=1)
        previous = self._read_monthly(code, prev_month.year, prev_month.month)

        if current is None:
            # Fall back to on-the-fly from raw tables
            start = date(ref_date.year, ref_date.month, 1)
            current = self._compute_live(code, start, ref_date)
            prev_start = date(prev_month.year, prev_month.month, 1)
            prev_end = prev_month
            previous = self._compute_live(code, prev_start, prev_end)

        return current, previous

    def _read_monthly(self, code: str, year: int, month: int) -> float | None:
        row = (
            self.db.query(KpiMensuel)
            .join(KpiDefinition)
            .filter(KpiDefinition.code == code, KpiMensuel.annee == year, KpiMensuel.mois == month)
            .first()
        )
        return float(row.valeur) if row and row.valeur is not None else None

    def _compute_live(self, code: str, start: date, end: date) -> float | None:
        try:
            return _LIVE_COMPUTERS.get(code, lambda *_: None)(self.db, start, end)
        except Exception as exc:
            log.warning("Live KPI compute failed for %s: %s", code, exc)
            return None

    @staticmethod
    def _trend(current: float | None, previous: float | None) -> float | None:
        if current is None or previous is None or previous == 0:
            return None
        return round((current - previous) / abs(previous) * 100, 1)

    def _empty_kpis(self) -> list[dict]:
        return [
            {
                "code": c,
                "label": FRIENDLY_LABELS.get(c, c),
                "value": None,
                "unit": "—",
                "color": "grey",
                "target": None,
                "trend": None,
            }
            for c in KPI_CODES_ORDERED
        ]


# ------------------------------------------------------------------
# Live computation functions — one per KPI code
# ------------------------------------------------------------------

def _compute_otif(db: Session, start: date, end: date) -> float | None:
    from app.models.demande import DemandeLocal, StatutDemande
    total = (
        db.query(func.count(DemandeLocal.id))
        .filter(DemandeLocal.date_livraison >= start, DemandeLocal.date_livraison <= end,
                DemandeLocal.statut == StatutDemande.LIVREE)
        .scalar() or 0
    )
    if total == 0:
        return None
    otif = (
        db.query(func.count(DemandeLocal.id))
        .filter(
            DemandeLocal.date_livraison >= start,
            DemandeLocal.date_livraison <= end,
            DemandeLocal.statut == StatutDemande.LIVREE,
            DemandeLocal.livree_a_temps == True,
            DemandeLocal.quantite_livree_kg >= DemandeLocal.quantite_kg,
        )
        .scalar() or 0
    )
    return round(otif / total * 100, 2)


def _compute_otd(db: Session, start: date, end: date) -> float | None:
    from app.models.demande import DemandeLocal, StatutDemande
    total_kg = (
        db.query(func.sum(DemandeLocal.quantite_livree_kg))
        .filter(DemandeLocal.date_livraison >= start, DemandeLocal.date_livraison <= end,
                DemandeLocal.statut == StatutDemande.LIVREE)
        .scalar() or 0
    )
    if total_kg == 0:
        return None
    on_time_kg = (
        db.query(func.sum(DemandeLocal.quantite_livree_kg))
        .filter(
            DemandeLocal.date_livraison >= start,
            DemandeLocal.date_livraison <= end,
            DemandeLocal.statut == StatutDemande.LIVREE,
            DemandeLocal.livree_a_temps == True,
        )
        .scalar() or 0
    )
    return round(float(on_time_kg) / float(total_kg) * 100, 2)


def _compute_premium_cost(db: Session, start: date, end: date) -> float | None:
    from app.models.plan import PlanMission, ModeMission
    val = (
        db.query(func.sum(PlanMission.cout_premium_eur))
        .filter(
            PlanMission.date_mission >= start,
            PlanMission.date_mission <= end,
            PlanMission.mode == ModeMission.PREMIUM,
        )
        .scalar()
    )
    return float(val) if val is not None else 0.0


def _compute_premium_count(db: Session, start: date, end: date) -> float | None:
    from app.models.plan import PlanMission, ModeMission
    val = (
        db.query(func.count(PlanMission.id))
        .filter(
            PlanMission.date_mission >= start,
            PlanMission.date_mission <= end,
            PlanMission.mode == ModeMission.PREMIUM,
        )
        .scalar() or 0
    )
    return float(val)


def _compute_fuel_efficiency(db: Session, start: date, end: date) -> float | None:
    from app.models.plan import PlanMission
    row = (
        db.query(
            func.sum(PlanMission.fuel_consomme_l).label("fuel"),
            func.sum(PlanMission.charge_kg).label("kg"),
            func.sum(PlanMission.km_parcourus).label("km"),
        )
        .filter(PlanMission.date_mission >= start, PlanMission.date_mission <= end)
        .first()
    )
    if not row or not row.fuel or not row.kg or not row.km:
        return None
    # mL / T.km  →  (litres × 1000) / (tonnes × km)
    return round(float(row.fuel) * 1000 / (float(row.kg) / 1000 * float(row.km)), 4)


def _compute_logistics_cost(db: Session, start: date, end: date) -> float | None:
    from app.models.plan import PlanMission
    row = (
        db.query(
            func.sum(PlanMission.cout_consommables_eur).label("cons"),
            func.sum(PlanMission.cout_emballage_eur).label("emb"),
            func.sum(PlanMission.cout_transport_eur).label("trans"),
            func.sum(PlanMission.charge_kg).label("kg"),
        )
        .filter(PlanMission.date_mission >= start, PlanMission.date_mission <= end)
        .first()
    )
    if not row or not row.kg or float(row.kg) == 0:
        return None
    total_eur = (float(row.cons or 0) + float(row.emb or 0) + float(row.trans or 0))
    tonnes = float(row.kg) / 1000
    return round(total_eur / tonnes, 2)


def _compute_incidents_per_mkm(db: Session, start: date, end: date) -> float | None:
    from app.models.plan import PlanMission
    from app.models.evenement import EvenementAlea, EvenementType
    km = (
        db.query(func.sum(PlanMission.km_parcourus))
        .filter(PlanMission.date_mission >= start, PlanMission.date_mission <= end)
        .scalar() or 0
    )
    if km == 0:
        return None
    incidents = (
        db.query(func.count(EvenementAlea.id))
        .filter(
            EvenementAlea.type == EvenementType.CLIENT_COMPLAINT,
            EvenementAlea.date_evenement >= start,
            EvenementAlea.date_evenement <= end,
        )
        .scalar() or 0
    )
    mkm = float(km) / 1_000_000
    return round(float(incidents) / mkm if mkm else 0, 4)


def _compute_load_efficiency(db: Session, start: date, end: date) -> float | None:
    from app.models.plan import PlanMission
    val = (
        db.query(func.avg(PlanMission.load_eff_pct))
        .filter(
            PlanMission.date_mission >= start,
            PlanMission.date_mission <= end,
            PlanMission.load_eff_pct.isnot(None),
        )
        .scalar()
    )
    return round(float(val), 2) if val is not None else None


_LIVE_COMPUTERS: dict[str, callable] = {
    "R4-06":   _compute_otif,
    "R4-02":   _compute_otd,
    "R4-02-PF": _compute_premium_cost,
    "R4-03":   _compute_premium_count,
    "R4-13":   _compute_fuel_efficiency,
    "R5-10":   _compute_logistics_cost,
    "R4-12":   _compute_incidents_per_mkm,
    "R4":      _compute_load_efficiency,
}
