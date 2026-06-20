"""Live control-tower snapshot (W3.2).

Turns a static daily plan into a *live* operational picture at a given wall-clock
time, without needing any external GPS feed:

  • interpolates every truck's current position along its planned route (depot →
    stops → depot), segment by segment, from the depart/arrival/return times the
    plan already carries;
  • classifies each truck's live state (pre-dispatch, en route, at a stop,
    reloading at depot, returning, completed);
  • raises predicted-late / geofence alerts: any stop whose projected arrival
    (after an injected delay) blows its hard delivery time-window is flagged, so a
    dispatcher sees the problem before the customer does.

Everything is deterministic and derived purely from the plan, so it is fully
unit-testable and reproducible — inject a delay on a truck and watch exactly
which downstream drops go red.
"""

from __future__ import annotations

from typing import Any, Optional


# ────────────────────────────────────────────────────────────── time helpers
def _to_min(value: Any) -> Optional[int]:
    """Parse an 'HH:MM' clock string into minutes since midnight. Late returns
    may exceed 24:00 (e.g. '25:14'); those keep counting, never clamped."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return None
    return hh * 60 + mm


def _clock(minutes: Optional[int]) -> Optional[str]:
    if minutes is None:
        return None
    m = max(0, int(minutes))
    return f"{m // 60:02d}:{m % 60:02d}"


def _coord(obj: Any) -> Optional[tuple[float, float]]:
    if not isinstance(obj, dict):
        return None
    lat = obj.get("lat", obj.get("latitude"))
    lon = obj.get("lon", obj.get("lng", obj.get("longitude")))
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if lat_f == 0 and lon_f == 0:
        return None
    return (lat_f, lon_f)


def _lerp(a: float, b: float, frac: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, frac))


def _window_end(stop: dict[str, Any]) -> Optional[int]:
    """Hard delivery time-window END (minutes), if the stop declares one."""
    window = (stop.get("constraints") or {}).get("time_window")
    if window and len(window) >= 2:
        return _to_min(window[1])
    return None


# ───────────────────────────────────────────────────────────── trip timeline
def _trip_segments(trip: dict[str, Any], depot: Optional[tuple[float, float]], delay: int):
    """Ordered movement segments of one trip, each shifted by `delay` minutes:
    a 'drive' depot→stop, a 'dwell' at the stop during service, drives between
    stops, and the final 'drive' back to the depot. Returns (segments, stops)
    where stops carries per-stop effective arrival / service-end + lateness."""
    segments: list[dict[str, Any]] = []
    stop_states: list[dict[str, Any]] = []

    depart = _to_min(trip.get("depart_at"))
    if depart is None:
        return segments, stop_states
    depart += delay

    prev_pt = depot
    prev_t = depart
    prev_label = "Depot"

    raw_stops = trip.get("stops") or []
    for stop in raw_stops:
        pt = _coord(stop)
        arrival = _to_min(stop.get("etd"))
        service_end = _to_min(stop.get("eta"))
        if arrival is None:
            continue
        arrival += delay
        service_end = (service_end + delay) if service_end is not None else arrival
        client = stop.get("client") or stop.get("end_location") or "stop"

        if prev_pt and pt and arrival > prev_t:
            segments.append({
                "kind": "drive", "t0": prev_t, "t1": arrival,
                "p0": prev_pt, "p1": pt, "from": prev_label, "to": client,
                "to_depot": False,
            })
        if pt and service_end > arrival:
            segments.append({
                "kind": "dwell", "t0": arrival, "t1": service_end,
                "p0": pt, "p1": pt, "from": client, "to": client,
                "to_depot": False,
            })

        win_end = _window_end(stop)
        minutes_late = (arrival - win_end) if (win_end is not None and arrival > win_end) else 0
        stop_states.append({
            "id": stop.get("id"),
            "client": client,
            "lat": pt[0] if pt else None,
            "lon": pt[1] if pt else None,
            "scheduled_eta": stop.get("etd"),
            "projected_arrival": _clock(arrival),
            "service_end_min": service_end,
            "arrival_min": arrival,
            "window_end": _clock(win_end) if win_end is not None else None,
            "minutes_late": int(minutes_late),
        })
        prev_pt = pt or prev_pt
        prev_t = service_end
        prev_label = client

    return_at = _to_min(trip.get("return_at"))
    if return_at is not None and prev_pt and depot:
        return_at += delay
        if return_at > prev_t:
            segments.append({
                "kind": "drive", "t0": prev_t, "t1": return_at,
                "p0": prev_pt, "p1": depot, "from": prev_label, "to": "Depot",
                "to_depot": True,
            })
    return segments, stop_states


# ───────────────────────────────────────────────────────────── per-truck state
def _truck_snapshot(truck: dict[str, Any], depot, now: int, delay: int) -> dict[str, Any]:
    trips = sorted(
        (t for t in (truck.get("trips") or []) if t.get("stops")),
        key=lambda t: (_to_min(t.get("depart_at")) or 0),
    )
    all_segments: list[dict[str, Any]] = []
    all_stops: list[dict[str, Any]] = []
    for trip in trips:
        segs, stops = _trip_segments(trip, depot, delay)
        for s in segs:
            s["trip_id"] = trip.get("trip_id")
        all_segments.extend(segs)
        all_stops.extend(stops)

    base = {
        "truck_id": truck.get("truck_id"),
        "truck_label": truck.get("truck_label"),
        "delay_min": int(delay),
        "total_stops": len(all_stops),
    }

    if not all_segments:
        return {**base, "state": "idle", "position": None, "from": None, "to": None,
                "segment_progress_pct": 0, "day_progress_pct": 0, "next_stop": None,
                "minutes_to_next_stop": None, "completed_stops": 0,
                "remaining_stops": len(all_stops), "late_stops": [], "current_trip_id": None}

    day_start = all_segments[0]["t0"]
    day_end = all_segments[-1]["t1"]
    day_progress = 0
    if day_end > day_start:
        day_progress = round(100 * (now - day_start) / (day_end - day_start))
    day_progress = max(0, min(100, day_progress))

    completed = sum(1 for s in all_stops if s["service_end_min"] <= now)
    # The next stop is the first one not yet serviced.
    upcoming = [s for s in all_stops if s["service_end_min"] > now]
    next_stop = None
    minutes_to_next = None
    if upcoming:
        nxt = upcoming[0]
        next_stop = {
            "client": nxt["client"], "lat": nxt["lat"], "lon": nxt["lon"],
            "eta": nxt["projected_arrival"],
        }
        minutes_to_next = max(0, nxt["arrival_min"] - now)

    # Where is the truck right now?
    state, position, seg_from, seg_to, seg_pct, current_trip = (
        None, None, None, None, 0, None)
    if now < day_start:
        state, position = "pre_dispatch", list(depot) if depot else None
    elif now >= day_end:
        state, position = "completed", list(depot) if depot else None
    else:
        active = next((s for s in all_segments if s["t0"] <= now < s["t1"]), None)
        if active is None:
            # In a gap between trips → back at the depot reloading.
            state, position = "reloading", list(depot) if depot else None
        else:
            frac = (now - active["t0"]) / (active["t1"] - active["t0"]) if active["t1"] > active["t0"] else 0
            seg_pct = round(100 * frac)
            seg_from, seg_to = active["from"], active["to"]
            current_trip = active.get("trip_id")
            p0, p1 = active["p0"], active["p1"]
            position = [_lerp(p0[0], p1[0], frac), _lerp(p0[1], p1[1], frac)]
            if active["kind"] == "dwell":
                state = "at_stop"
            elif active.get("to_depot"):
                state = "returning"
            else:
                state = "en_route"

    late_stops = [
        {
            "id": s["id"], "client": s["client"], "lat": s["lat"], "lon": s["lon"],
            "scheduled_eta": s["scheduled_eta"], "projected_arrival": s["projected_arrival"],
            "window_end": s["window_end"], "minutes_late": s["minutes_late"],
            "upcoming": s["service_end_min"] > now,
        }
        for s in all_stops if s["minutes_late"] > 0
    ]

    return {
        **base,
        "state": state,
        "position": position,
        "from": seg_from,
        "to": seg_to,
        "segment_progress_pct": seg_pct,
        "day_progress_pct": day_progress,
        "current_trip_id": current_trip,
        "next_stop": next_stop,
        "minutes_to_next_stop": minutes_to_next,
        "completed_stops": completed,
        "remaining_stops": len(all_stops) - completed,
        "late_stops": late_stops,
    }


def _normalize_delays(delays: Any) -> dict[str, int]:
    """Accept {truck_id: minutes} or [{truck_id, delay_min}] → {str(id): minutes}."""
    out: dict[str, int] = {}
    if isinstance(delays, dict):
        for k, v in delays.items():
            try:
                out[str(k)] = int(v)
            except (TypeError, ValueError):
                continue
    elif isinstance(delays, list):
        for item in delays:
            if not isinstance(item, dict):
                continue
            tid = item.get("truck_id")
            mins = item.get("delay_min", item.get("minutes"))
            if tid is None:
                continue
            try:
                out[str(tid)] = int(mins)
            except (TypeError, ValueError):
                continue
    return out


def _default_now(plan: dict[str, Any], delays: dict[str, int]) -> int:
    """Mid-point of the working day (earliest depart ↔ latest return) so a demo
    snapshot lands mid-operation with trucks visibly on the road."""
    deps, rets = [], []
    for t in plan.get("trucks", []):
        delay = delays.get(str(t.get("truck_id")), 0)
        for trip in t.get("trips") or []:
            d = _to_min(trip.get("depart_at"))
            r = _to_min(trip.get("return_at"))
            if d is not None:
                deps.append(d + delay)
            if r is not None:
                rets.append(r + delay)
    if not deps or not rets:
        return 12 * 60
    return (min(deps) + max(rets)) // 2


# ─────────────────────────────────────────────────────────────── public API
def live_snapshot(
    plan: dict[str, Any],
    now_min: Optional[int] = None,
    delays: Any = None,
) -> dict[str, Any]:
    """Build a live control-tower snapshot of `plan` at `now_min` (minutes since
    midnight; defaults to the mid-point of the day). `delays` injects per-truck
    minutes-behind, shifting that truck's whole timeline and surfacing any stop
    whose projected arrival then misses its hard delivery window."""
    delays_map = _normalize_delays(delays)
    if now_min is None:
        now_min = _default_now(plan, delays_map)
    now_min = int(now_min)

    depot = _coord(plan.get("depot"))
    trucks_out = []
    for truck in plan.get("trucks", []):
        delay = delays_map.get(str(truck.get("truck_id")), 0)
        trucks_out.append(_truck_snapshot(truck, depot, now_min, delay))

    # Fleet roll-up.
    by_state: dict[str, int] = {}
    for t in trucks_out:
        by_state[t["state"]] = by_state.get(t["state"], 0) + 1

    alerts = []
    for t in trucks_out:
        for s in t["late_stops"]:
            alerts.append({
                "truck_id": t["truck_id"],
                "truck_label": t["truck_label"],
                "client": s["client"],
                "lat": s["lat"], "lon": s["lon"],
                "scheduled_eta": s["scheduled_eta"],
                "projected_arrival": s["projected_arrival"],
                "window_end": s["window_end"],
                "minutes_late": s["minutes_late"],
                "upcoming": s["upcoming"],
                "severity": "high" if s["minutes_late"] > 60 else "warning",
            })
    alerts.sort(key=lambda a: a["minutes_late"], reverse=True)

    active_states = {"en_route", "at_stop", "returning"}
    return {
        "as_of": _clock(now_min),
        "as_of_minutes": now_min,
        "depot": {"lat": depot[0], "lon": depot[1]} if depot else None,
        "fleet": {
            "total_trucks": len(trucks_out),
            "active": sum(1 for t in trucks_out if t["state"] in active_states),
            "en_route": by_state.get("en_route", 0),
            "at_stop": by_state.get("at_stop", 0),
            "returning": by_state.get("returning", 0),
            "reloading": by_state.get("reloading", 0),
            "idle": by_state.get("idle", 0) + by_state.get("pre_dispatch", 0),
            "completed": by_state.get("completed", 0),
            "stops_done": sum(t["completed_stops"] for t in trucks_out),
            "stops_total": sum(t["total_stops"] for t in trucks_out),
            "predicted_late_stops": sum(1 for a in alerts if a["upcoming"]),
            "late_stops_total": len(alerts),
        },
        "trucks": trucks_out,
        "alerts": alerts,
    }
