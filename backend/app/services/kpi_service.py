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
import os
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, case, func

from app.models.kpi import KpiDefinition, KpiJournalier, KpiMensuel, KpiStatus

log = logging.getLogger(__name__)

DEFAULT_DIESEL_CO2E_KG_PER_L = 2.68

# KPI catalog ordered as dashboard expects
KPI_CODES_ORDERED = ["R4-06", "R4-02", "R4-02-PF", "R4-03", "R4-13", "R5-10", "R4-12", "R4"]

FRIENDLY_LABELS = {
    "R4-06":   "Load Efficiency Rate",
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


def fuel_efficiency_ml_per_tkm(fuel_l, tonne_km) -> float | None:
    """Convert fuel and transport work into the official mL/tonne-km KPI."""
    if fuel_l is None or tonne_km is None or float(tonne_km) <= 0:
        return None
    return round(float(fuel_l) * 1000 / float(tonne_km), 4)


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

    def get_weekly_delivery_trend(
        self,
        weeks: int = 8,
        ref_date: date | None = None,
    ) -> list[dict]:
        """Weekly aggregates using ISO-8601 week years and numbers."""
        from app.models.demande import DemandeLocal, StatutDemande
        today = ref_date or date.today()
        rows = []
        for w in range(weeks - 1, -1, -1):
            start = today - timedelta(days=today.weekday() + 7 * w)
            end = start + timedelta(days=6)
            iso_year, iso_week, _ = start.isocalendar()
            q = self.db.query(
                func.count(DemandeLocal.id).label("total"),
                func.sum(
                    case(
                        (DemandeLocal.statut == StatutDemande.LIVREE, 1),
                        else_=0,
                    )
                ).label("delivered"),
                func.sum(
                    case(
                        (
                            and_(
                                DemandeLocal.statut == StatutDemande.LIVREE,
                                DemandeLocal.livree_a_temps.is_(True),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("on_time"),
            ).filter(
                DemandeLocal.date_livraison >= start,
                DemandeLocal.date_livraison <= end,
            ).first()
            rows.append({
                "week": f"W{iso_week:02d}",
                "label": f"W{iso_week:02d}",
                "period": f"{iso_year}-W{iso_week:02d}",
                "iso_year": iso_year,
                "iso_week": iso_week,
                "date": start.isoformat(),
                "total": int(q.total or 0),
                "delivered": int(q.delivered or 0),
                "on_time": int(q.on_time or 0),
            })
        return rows

    def get_operational_summary(
        self,
        start: date,
        end: date,
    ) -> dict[str, float | None]:
        """Return auditable distance and fuel totals for a reporting period."""
        from app.models.plan import PlanMission, StatutMission

        row = (
            self.db.query(
                func.sum(PlanMission.km_parcourus).label("distance_km"),
                func.sum(PlanMission.fuel_consomme_l).label("fuel_l"),
                func.sum(
                    (PlanMission.charge_kg / 1000.0) * PlanMission.km_parcourus
                ).label("tonne_km"),
            )
            .filter(
                PlanMission.date_mission >= start,
                PlanMission.date_mission <= end,
                PlanMission.statut == StatutMission.TERMINEE,
            )
            .first()
        )
        distance_km = float(row.distance_km or 0) if row else 0.0
        fuel_l = float(row.fuel_l or 0) if row else 0.0
        tonne_km = float(row.tonne_km or 0) if row else 0.0
        return {
            "distance_travelled_km": round(distance_km, 2),
            "fuel_consumed_l": round(fuel_l, 2),
            "tonne_km": round(tonne_km, 2),
            "fuel_l_per_100km": (
                round(fuel_l * 100 / distance_km, 4) if distance_km > 0 else None
            ),
        }

    def get_carbon_history(
        self,
        start: date,
        end: date,
        group_by: str = "week",
        emission_factor: float | None = None,
    ) -> dict:
        """Aggregate fuel-based CO2e history without changing OTIF semantics."""
        from app.models.plan import PlanMission, StatutMission

        if end < start:
            raise ValueError("end date must be on or after start date")
        if group_by not in {"day", "week", "month"}:
            raise ValueError("group_by must be one of: day, week, month")
        factor = emission_factor
        if factor is None:
            factor = float(
                os.getenv(
                    "DIESEL_CO2E_KG_PER_L",
                    str(DEFAULT_DIESEL_CO2E_KG_PER_L),
                )
            )
        if factor <= 0:
            raise ValueError("emission factor must be greater than zero")

        missions = (
            self.db.query(
                PlanMission.date_mission,
                PlanMission.fuel_consomme_l,
                PlanMission.km_parcourus,
                PlanMission.charge_kg,
            )
            .filter(
                PlanMission.date_mission >= start,
                PlanMission.date_mission <= end,
                PlanMission.statut == StatutMission.TERMINEE,
            )
            .order_by(PlanMission.date_mission)
            .all()
        )
        buckets: dict[date, dict[str, float]] = {}
        for mission in missions:
            period_start = self._carbon_period_start(mission.date_mission, group_by)
            bucket = buckets.setdefault(
                period_start,
                {"fuel_l": 0.0, "distance_km": 0.0, "tonne_km": 0.0},
            )
            fuel_l = float(mission.fuel_consomme_l or 0)
            distance_km = float(mission.km_parcourus or 0)
            charge_t = float(mission.charge_kg or 0) / 1000
            bucket["fuel_l"] += fuel_l
            bucket["distance_km"] += distance_km
            bucket["tonne_km"] += charge_t * distance_km

        history = [
            self._carbon_bucket_payload(period_start, values, factor, group_by)
            for period_start, values in sorted(buckets.items())
        ]
        totals = {
            "fuel_l": sum(row["fuel_l"] for row in history),
            "distance_km": sum(row["distance_km"] for row in history),
            "tonne_km": sum(row["tonne_km"] for row in history),
        }
        summary = self._carbon_values(totals, factor)
        return {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "group_by": group_by,
            "factor": {
                "kg_co2e_per_l": factor,
                "source": os.getenv(
                    "CARBON_FACTOR_SOURCE",
                    "project default - replace with an approved Coficab source",
                ),
                "boundary": os.getenv(
                    "CARBON_FACTOR_BOUNDARY",
                    "tank-to-wheel estimate",
                ),
                "effective_from": os.getenv(
                    "CARBON_FACTOR_EFFECTIVE_FROM",
                    "unversioned",
                ),
                "configuration_key": "DIESEL_CO2E_KG_PER_L",
            },
            "summary": summary,
            "history": history,
        }

    @staticmethod
    def _carbon_period_start(value: date, group_by: str) -> date:
        if group_by == "day":
            return value
        if group_by == "week":
            return value - timedelta(days=value.weekday())
        return value.replace(day=1)

    @classmethod
    def _carbon_bucket_payload(
        cls,
        period_start: date,
        values: dict[str, float],
        factor: float,
        group_by: str,
    ) -> dict:
        if group_by == "week":
            iso_year, iso_week, _ = period_start.isocalendar()
            period = f"{iso_year}-W{iso_week:02d}"
            label = f"W{iso_week:02d}"
        elif group_by == "month":
            period = period_start.strftime("%Y-%m")
            label = period
        else:
            period = period_start.isoformat()
            label = period_start.strftime("%d %b")
        return {
            "period": period,
            "label": label,
            "date": period_start.isoformat(),
            **cls._carbon_values(values, factor),
        }

    @staticmethod
    def _carbon_values(values: dict[str, float], factor: float) -> dict:
        fuel_l = float(values["fuel_l"])
        distance_km = float(values["distance_km"])
        tonne_km = float(values["tonne_km"])
        emissions = fuel_l * factor
        return {
            "fuel_l": round(fuel_l, 2),
            "distance_km": round(distance_km, 2),
            "tonne_km": round(tonne_km, 2),
            "emissions_kg_co2e": round(emissions, 3),
            "kg_co2e_per_km": (
                round(emissions / distance_km, 6) if distance_km > 0 else None
            ),
            "kg_co2e_per_tonne_km": (
                round(emissions / tonne_km, 6) if tonne_km > 0 else None
            ),
        }

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
    from app.models.plan import PlanMission, StatutMission
    row = (
        db.query(
            func.sum(PlanMission.fuel_consomme_l).label("fuel"),
            func.sum(
                (PlanMission.charge_kg / 1000.0) * PlanMission.km_parcourus
            ).label("tonne_km"),
        )
        .filter(
            PlanMission.date_mission >= start,
            PlanMission.date_mission <= end,
            PlanMission.statut == StatutMission.TERMINEE,
        )
        .first()
    )
    if not row or not row.fuel or not row.tonne_km:
        return None
    # mL / T.km  →  (litres × 1000) / (tonnes × km)
    return fuel_efficiency_ml_per_tkm(row.fuel, row.tonne_km)


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
