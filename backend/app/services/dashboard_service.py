"""Operations-dashboard metrics derived from the generated daily plan.

The dashboard used to render hard-coded mock numbers. This module turns a real
DailyPlanBuilder plan (which works offline from the weekly workbook + client
directory, and already reflects the live scheduling rules — depart-by-18:00,
early long-haul starts, capacity splits) into the KPI cards, fleet-health bars,
route-efficiency donut, recent-activity feed, alerts and a Mon→Sun trend the
dashboard needs. Everything here is computed from the plan, so the dashboard
always agrees with the Generated Daily Planning screen.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

log = logging.getLogger(__name__)

_BAND_COLORS = {
    "Optimized": "#7c3aed",
    "Good": "#3b82f6",
    "Average": "#f59e0b",
    "Below Avg": "#ef4444",
}

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Heavy-truck gasoil burn used to derive litres consumed from route distance,
# matching DailyPlanBuilder's planning assumption (L per 100 km).
FUEL_L_PER_100KM = 28.0


def _positions(stop: dict[str, Any]) -> float:
    return float(stop.get("quantity_positions") or stop.get("position_count") or 0)


def _trip_positions(trip: dict[str, Any]) -> float:
    return sum(_positions(s) for s in trip.get("stops", []))


def _gross_kg(stop: dict[str, Any]) -> float:
    """Real gross weight for a stop, read from the workbook row."""
    raw = stop.get("raw") or {}
    return float(raw.get("gross_weight_kg") or raw.get("total_gross_weight_kg") or 0)


def _requested_etd(stop: dict[str, Any]) -> Optional[int]:
    """The customer's requested ETD (minutes) from the workbook row."""
    raw = stop.get("raw") or {}
    return _hhmm_to_minutes(raw.get("etd"))


def _scheduled_arrival(stop: dict[str, Any]) -> Optional[int]:
    """The plan's scheduled ARRIVAL at the stop (minutes).

    On-Time Delivery is measured against when the truck reaches the client, not
    when it leaves the depot. Note the field-naming quirk in DailyPlanBuilder
    output: a stop's ``etd`` key holds the computed arrival time, while ``eta``
    holds arrival+service (the departure after loading).
    """
    return _hhmm_to_minutes(stop.get("etd"))


def _hhmm_to_minutes(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        h, m = str(value).split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, TypeError):
        return None


def _trip_status(trip: dict[str, Any], now_minutes: Optional[int]) -> str:
    """completed / in_transit / pending relative to `now` (today only)."""
    if now_minutes is None:
        return "pending"
    depart = _hhmm_to_minutes(trip.get("depart_at"))
    ret = _hhmm_to_minutes(trip.get("return_at"))
    if ret is not None and now_minutes >= ret:
        return "completed"
    if depart is not None and now_minutes >= depart:
        return "in_transit"
    return "pending"


def _all_trips(plan: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [(t, tr) for t in plan.get("trucks", []) for tr in t.get("trips", [])]


def plan_metrics(plan: dict[str, Any], avg_speed_kmh: float, ref_day: date) -> dict[str, Any]:
    """Detailed dashboard payload for a single day's plan."""
    trucks = plan.get("trucks", [])
    unassigned = plan.get("unassigned", [])
    trips = _all_trips(plan)

    deliveries = sum(len(tr.get("stops", [])) for _, tr in trips)
    positions_planned = sum(_trip_positions(tr) for _, tr in trips)
    unassigned_positions = sum(_positions(u) for u in unassigned)

    # ---- fleet health: average fill across each truck's trips --------------
    fleet: list[dict[str, Any]] = []
    util_values: list[int] = []
    for t in trucks:
        truck_trips = t.get("trips", [])
        if not truck_trips:
            continue
        cap = float(t.get("capacity_positions") or 0) or 1.0
        pos = sum(_trip_positions(tr) for tr in truck_trips)
        util = round(100 * pos / (cap * len(truck_trips)))
        util_values.append(util)
        kg = int(float(t.get("capacity_kg") or 0))
        fleet.append({
            "name": t.get("truck_label") or f"Truck {t.get('truck_id')}",
            "type": f"{int(cap)} pal · {kg:,} kg".replace(",", " "),
            "utilization": util,
            "trips": len(truck_trips),
            "positions": int(pos),
            "capacity": int(cap),
        })
    fleet.sort(key=lambda f: f["utilization"], reverse=True)
    avg_util = round(sum(util_values) / len(util_values)) if util_values else 0

    # ---- route-efficiency donut: trips bucketed by fill band ---------------
    bands = {"Optimized": 0, "Good": 0, "Average": 0, "Below Avg": 0}
    for t, tr in trips:
        cap = float(t.get("capacity_positions") or 0) or 1.0
        u = 100 * _trip_positions(tr) / cap
        if u >= 90:
            bands["Optimized"] += 1
        elif u >= 80:
            bands["Good"] += 1
        elif u >= 60:
            bands["Average"] += 1
        else:
            bands["Below Avg"] += 1
    trip_count = sum(bands.values()) or 1
    efficiency = [
        {"name": name, "value": round(100 * count / trip_count), "color": _BAND_COLORS[name], "count": count}
        for name, count in bands.items()
    ]

    # ---- distance (real road km legs) + real gross weight ------------------
    drive_min = 0.0
    total_gross_kg = 0.0
    for _, tr in trips:
        stops = tr.get("stops", [])
        drive_min += sum(float(s.get("travel_min") or 0) for s in stops)
        if stops:  # return leg back to the depot ≈ last stop's depot distance
            drive_min += float(stops[-1].get("distance_km") or 0) / avg_speed_kmh * 60.0
        total_gross_kg += sum(_gross_kg(s) for s in stops)
    total_km = round(drive_min / 60.0 * avg_speed_kmh)

    # ---- recent route activity --------------------------------------------
    now_minutes = (datetime.now().hour * 60 + datetime.now().minute) if ref_day == date.today() else None
    activity = []
    for t, tr in sorted(trips, key=lambda x: x[1].get("depart_at") or ""):
        stops = tr.get("stops", [])
        dests = list(dict.fromkeys(
            (s.get("resolved_location") or s.get("client") or "").split(" (")[0] for s in stops
        ))
        where = ", ".join(d for d in dests if d)[:48]
        activity.append({
            "id": tr.get("trip_id"),
            "route": t.get("truck_label") or f"Truck {t.get('truck_id')}",
            "description": f"{len(stops)} stop(s) · {int(_trip_positions(tr))} pos → {where}",
            "time": f"{tr.get('depart_at')}–{tr.get('return_at')}",
            "status": _trip_status(tr, now_minutes),
        })

    # ---- alerts: unassigned (critical) + under-filled trips (warning) ------
    alerts = []
    for u in unassigned:
        alerts.append({
            "id": f"un-{u.get('id')}",
            "severity": "critical",
            "title": f"Unassigned: {u.get('client')}",
            "description": u.get("unassigned_reason") or "Needs dispatcher review",
            "icon": "alert-triangle",
        })
    for under in (plan.get("diagnostics") or {}).get("under_80pct_departures", []):
        alerts.append({
            "id": f"under-{under.get('trip')}",
            "severity": "warning",
            "title": f"{under.get('truck')} under target ({under.get('utilization_pct')}%)",
            "description": under.get("reason") or "Departure below the 80% fill target",
            "icon": "clock",
        })

    return {
        "fleet": fleet,
        "efficiency": efficiency,
        "efficiency_score": avg_util,
        "activity": activity,
        "alerts": alerts,
        "totals": {
            "deliveries": deliveries,
            "positions_planned": int(positions_planned),
            "positions_unassigned": int(unassigned_positions),
            "active_trucks": len(fleet),
            "avg_utilization": avg_util,
            "distance_km": total_km,
            "gross_weight_kg": round(total_gross_kg),
            "tonnes": round(total_gross_kg / 1000.0, 1),
            "premium_trips": sum(
                len(t.get("trips", [])) for t in trucks
                if str(t.get("truck_id")) == str(RENTED_TRUCK_ID)
            ),
        },
    }


# Truck id used for the hired/rented vehicle (matches DailyPlanBuilder).
RENTED_TRUCK_ID = 999

# KPI colour bands: (target, green-threshold, yellow-threshold, direction).
# direction "up" = higher is better; "down" = lower is better.
_KPI_BANDS = {
    "otif": (95.0, 95.0, 85.0, "up"),
    "otd": (95.0, 95.0, 85.0, "up"),
    "load": (80.0, 80.0, 65.0, "up"),
    "fuel": (0.02, 0.02, 0.03, "down"),  # L/T·km — lower is better
}


def _band(value: Optional[float], green: float, yellow: float, direction: str) -> str:
    if value is None:
        return "grey"
    if direction == "up":
        if value >= green:
            return "green"
        return "yellow" if value >= yellow else "red"
    if value <= green:
        return "green"
    return "yellow" if value <= yellow else "red"


# Each KPI is pooled into a running accumulator across however many days of
# real travels we average over, then finalised once. Pooling weights every KPI
# by real volume (positions / kg), so the average is volume-weighted, not a
# mean-of-daily-means.

def _new_kpi_acc() -> dict[str, float]:
    return {
        "on_time_pos": 0.0,        # positions delivered on the demanded day (assigned)
        "in_full_on_time_pos": 0.0,  # positions of orders delivered in full on the day
        "demanded_pos": 0.0,       # all positions demanded that day (assigned + unassigned)
        "trip_pos": 0.0,        # positions loaded across all trips
        "trip_cap_pos": 0.0,    # position capacity deployed (per trip)
        "weighted_gross_kg": 0.0,  # gross kg on trips that declare weight
        "weighted_cap_kg": 0.0,    # kg capacity of those same trips
        "gross_kg_total": 0.0,     # tonnage transported (all stops) — for fuel KPI
    }


def _delivery_id(stop: dict[str, Any]) -> str:
    """Stable key to group a delivery's parts (same-day splits share an id)."""
    raw = stop.get("raw") or {}
    return str(stop.get("id") or raw.get("row_number") or raw.get("id")
               or f"{stop.get('client')}|{_positions(stop)}")


def _accumulate_kpis(plan: dict[str, Any], acc: dict[str, float]) -> None:
    """Fold one day's real travels into the KPI accumulator.

    OTD/OTIF are measured by DAY, not by time of day: the requested ETD time is
    only a proposal (it matters when urgent), so it is ignored here. Because each
    day's plan delivers exactly that day's demand, every assigned position is
    "on time" (delivered on the demanded day); a position misses only when it is
    left unassigned (pushed to another day). "In full" means the whole order was
    delivered — same-day splits across trucks still count; an order left short
    (part unassigned) does not.
    """
    demand: dict[str, list[float]] = {}  # delivery id -> [assigned_pos, unassigned_pos]
    for t in plan.get("trucks", []):
        cap_pos = float(t.get("capacity_positions") or 0)
        cap_kg = float(t.get("capacity_kg") or 0)
        for tr in t.get("trips", []):
            stops = tr.get("stops", [])
            acc["trip_pos"] += sum(_positions(s) for s in stops)
            acc["trip_cap_pos"] += cap_pos
            trip_gross = 0.0
            has_weight = False
            for s in stops:
                pos = _positions(s)
                gk = _gross_kg(s)
                trip_gross += gk
                acc["gross_kg_total"] += gk
                has_weight = has_weight or gk > 0
                demand.setdefault(_delivery_id(s), [0.0, 0.0])[0] += pos
            if has_weight:
                acc["weighted_gross_kg"] += trip_gross
                acc["weighted_cap_kg"] += cap_kg
    # Unassigned demand = not delivered on the demanded day → fails OTD/OTIF.
    for u in plan.get("unassigned", []):
        demand.setdefault(_delivery_id(u), [0.0, 0.0])[1] += _positions(u)

    for assigned, unassigned in demand.values():
        acc["demanded_pos"] += assigned + unassigned
        acc["on_time_pos"] += assigned                 # delivered on the demanded day
        if unassigned == 0:                            # order delivered in full
            acc["in_full_on_time_pos"] += assigned


def _finalize_kpis(acc: dict[str, float]) -> list[dict[str, Any]]:
    """Turn the pooled accumulator into the 4 KPI cards (the period average).

    All from the REAL workbook columns (requested ETD, Position Nbr, Gross
    weight) + real fleet capacities — no fabricated factors:
      • OTIF — positions of orders delivered in full on the demanded day ÷ demand
      • Load Efficiency — positions loaded ÷ position capacity
      • OTD  — positions delivered on the demanded day ÷ demand
      • Fuel consumption / tonnage — litres of gasoil per tonne-kilometre
    """
    demanded = acc["demanded_pos"]
    otd = round(100.0 * acc["on_time_pos"] / demanded, 1) if demanded else None
    otif = round(100.0 * acc["in_full_on_time_pos"] / demanded, 1) if demanded else None
    load_eff = round(100.0 * acc["trip_pos"] / acc["trip_cap_pos"], 1) if acc["trip_cap_pos"] else None

    # Fuel consumption per tonnage transported = fuel_L × 1000 / (kg × km).
    # Fuel burned ≈ route_km × FUEL_L_PER_100KM/100, so the route km cancels with
    # the km in the denominator and the spec formula reduces to a function of the
    # tonnage carried: (FUEL_L_PER_100KM/100 × 1000) / kg = FUEL_L_PER_100KM×10/kg.
    gross_kg = acc["gross_kg_total"]
    fuel_eff = round(FUEL_L_PER_100KM * 10.0 / gross_kg, 4) if gross_kg else None

    raw = [
        ("R4-06", "otif", "Load Efficiency Rate", otif, "%", "truck", "delivered in full on the demanded day"),
        ("R4", "load", "Load Efficiency", load_eff, "%", "gauge", "positions ÷ capacity"),
        ("R4-02", "otd", "OTD", otd, "%", "clock", "delivered on the demanded day"),
        ("R4-13", "fuel", "Fuel / Tonnage", fuel_eff, "L/T·km", "gauge", "fuel ÷ (tonnage × distance)"),
    ]
    kpis = []
    for code, kid, label, value, unit, icon, hint in raw:
        target, green, yellow, direction = _KPI_BANDS[kid]
        kpis.append({
            "code": code,
            "id": kid,
            "label": label,
            "value": value,
            "unit": unit,
            "target": target,
            "color": _band(value, green, yellow, direction),
            "direction": direction,
            "icon": icon,
            "hint": hint,
            "basis": "planned-average",
        })
    return kpis


def plan_kpis(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """KPIs for a single day's plan."""
    acc = _new_kpi_acc()
    _accumulate_kpis(plan, acc)
    return _finalize_kpis(acc)


def week_bounds(ref_day: date) -> list[date]:
    """The Mon→Sun dates of the week containing ref_day."""
    monday = ref_day - timedelta(days=ref_day.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def _weekly_row(plan: Optional[dict[str, Any]], d: date) -> dict[str, Any]:
    label = _WEEKDAYS[d.weekday()]
    if not plan:
        return {"day": label, "date": d.isoformat(), "delivered": 0, "planned": 0, "trucks": 0}
    trips = _all_trips(plan)
    delivered = int(sum(_trip_positions(tr) for _, tr in trips))
    unassigned_pos = int(sum(_positions(u) for u in plan.get("unassigned", [])))
    return {
        "day": label,
        "date": d.isoformat(),
        "delivered": delivered,
        "planned": delivered + unassigned_pos,
        "trucks": len([t for t in plan.get("trucks", []) if t.get("trips")]),
    }


PERIODS = ("daily", "weekly", "monthly")


def period_dates(period: str, ref_day: date) -> list[date]:
    """The dates whose plans are pooled into the KPI average for `period`:
      • daily   — just the reference day
      • weekly  — the Mon→Sun week containing it
      • monthly — the 1st of the month up to (and including) the reference day
    """
    if period == "daily":
        return [ref_day]
    if period == "monthly":
        start = ref_day.replace(day=1)
        return [start + timedelta(days=i) for i in range((ref_day - start).days + 1)]
    return week_bounds(ref_day)


def period_range(period: str, ref_day: date) -> tuple[date, date]:
    """The [start, end] dates the KPI cards are computed over for `period`."""
    dates = period_dates(period if period in PERIODS else "weekly", ref_day)
    return dates[0], dates[-1]


def _kpi_period_meta(period: str, ref_day: date, dates: list[date], days_used: int) -> dict[str, Any]:
    month = ref_day.strftime("%B %Y")
    if period == "daily":
        label = ref_day.strftime("%A, %d %B %Y")
    elif period == "monthly":
        label = month
    else:
        label = f"{dates[0].strftime('%d %b')} → {dates[-1].strftime('%d %b')}"
    return {
        "period": period,
        "label": label,
        "month": month,
        "range": f"{dates[0].isoformat()} → {dates[-1].isoformat()}",
        "days": days_used,
    }


def period_dashboard(
    build_for_day, ref_day: date, avg_speed_kmh: float, period: str = "weekly",
    load_eff_fn=None,
) -> dict[str, Any]:
    """Build the days the dashboard needs once and return:
      • kpis       — the volume-weighted AVERAGE of each KPI over the chosen
                     `period` (daily / weekly / monthly)
      • kpi_period — the label/range/day-count describing that window
      • weekly     — the Mon→Sun planned-vs-delivered trend (always, for context)
      • the ref-day plan's fleet/efficiency/activity/alerts/totals panels

    `build_for_day(d)` returns a plan dict (or raises); a failed day is skipped
    from the average but still shown as an empty bar in the trend.

    `load_eff_fn(plan) -> float | None`, when given, replaces the Load Efficiency
    KPI value with the average of its per-day result over the period (used to
    source Load Efficiency from the same VRPTW optimiser as the generated-planning
    page, so the two screens agree).
    """
    period = period if period in PERIODS else "weekly"
    kpi_dates = period_dates(period, ref_day)
    week = week_bounds(ref_day)

    # Build each needed day exactly once — the KPI window and the Mon→Sun trend
    # can overlap, and for monthly the week is a subset of the month.
    plans: dict[date, Optional[dict[str, Any]]] = {}
    for d in sorted(set(kpi_dates) | set(week)):
        try:
            plans[d] = build_for_day(d)
        except Exception:
            plans[d] = None

    acc = _new_kpi_acc()
    days_used = 0
    for d in kpi_dates:
        plan = plans.get(d)
        if plan:
            _accumulate_kpis(plan, acc)
            days_used += 1

    weekly = [_weekly_row(plans.get(d), d) for d in week]

    ref_plan = plans.get(ref_day) or build_for_day(ref_day)
    metrics = plan_metrics(ref_plan, avg_speed_kmh, ref_day)

    kpis = _finalize_kpis(acc)
    if load_eff_fn is not None:
        _override_load_efficiency(kpis, plans, kpi_dates, load_eff_fn)

    return {
        "generated_at": ref_plan.get("generated_at"),
        "source_file": ref_plan.get("source_file"),
        "kpis": kpis,
        "kpi_period": _kpi_period_meta(period, ref_day, kpi_dates, days_used),
        "weekly": weekly,
        **metrics,
    }


def _override_load_efficiency(kpis, plans, kpi_dates, load_eff_fn) -> None:
    """Replace the 'load' KPI value with the period-average of `load_eff_fn`
    (one value per day with a plan). Leaves it untouched if nothing computes."""
    values = []
    for d in kpi_dates:
        plan = plans.get(d)
        if not plan:
            continue
        try:
            v = load_eff_fn(plan)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Load-efficiency override failed for %s: %s", d, exc)
            v = None
        if v is not None:
            values.append(float(v))
    if not values:
        return
    avg = round(sum(values) / len(values), 1)
    target, green, yellow, direction = _KPI_BANDS["load"]
    for card in kpis:
        if card.get("id") == "load":
            card["value"] = avg
            card["color"] = _band(avg, green, yellow, direction)
            card["hint"] = "truck fill from the planning optimiser"
            break
