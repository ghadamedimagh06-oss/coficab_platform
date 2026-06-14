"""Monte-Carlo plan-confidence simulator (W2.3).

A generated daily plan gives deterministic ETAs, but real days vary: traffic,
loading delays, the occasional breakdown. This module replays a plan many times
with randomised travel/service times (plus rare disruption spikes) and reports
how robust the plan actually is:

  * expected OTIF — the mean on-time-in-full % across runs (the headline service
                    level you can expect on a typical day);
  * reliability % — share of simulated days that still hit an OTIF target
                    (default 90%) — i.e. how often the plan is "good enough";
  * finish times  — P50 / P90 of when the last truck gets home;
  * fragile stops — the deliveries that miss most often, with their late-rate.

Deterministic by default (seeded) so a demo is stable run-to-run.
"""

from __future__ import annotations

import random
from typing import Any, Optional


def _minutes(clock: Any) -> Optional[int]:
    try:
        hh, mm = str(clock).split(":")[:2]
        return int(hh) * 60 + int(mm)
    except (ValueError, AttributeError):
        return None


def _clock(minutes: Optional[float]) -> Optional[str]:
    if minutes is None:
        return None
    m = max(0, int(round(minutes)))
    return f"{m // 60:02d}:{m % 60:02d}"


def _percentile(sorted_vals: list[float], p: float) -> Optional[float]:
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, max(0, int(round(p / 100.0 * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def simulate_plan(
    plan: dict[str, Any],
    runs: int = 500,
    travel_sigma: float = 0.20,
    service_sigma: float = 0.15,
    disruption_prob: float = 0.06,
    disruption_extra_min: tuple[float, float] = (15.0, 45.0),
    grace_minutes: int = 15,
    otif_target: float = 90.0,
    seed: int = 42,
) -> dict[str, Any]:
    """Replay ``plan`` ``runs`` times under randomised durations.

    Noise model: each leg's travel and on-site service time is multiplied by an
    independent lognormal factor (median 1.0); with probability ``disruption_prob``
    a leg additionally takes a uniform random delay spike. A stop is "on time" if
    its simulated arrival is within its workbook time window, or — when it has no
    window — within its planned arrival plus ``grace_minutes``.
    """
    rng = random.Random(seed)
    trucks = plan.get("trucks", [])

    # Pre-extract the legs we re-walk, so the hot loop is cheap.
    routes = []  # list of (truck_label, [stops], depart, return_leg_min)
    total_stops = 0
    for t in trucks:
        for trip in t.get("trips", []):
            stops = trip.get("stops", [])
            if not stops:
                continue
            depart = _minutes(trip.get("depart_at")) or 0
            last_eta = _minutes(stops[-1].get("eta"))
            ret = _minutes(trip.get("return_at"))
            return_leg = max(0.0, (ret - last_eta)) if (ret is not None and last_eta is not None) else 0.0
            routes.append((t.get("truck_label"), stops, depart, return_leg))
            total_stops += len(stops)

    if total_stops == 0:
        return {
            "runs": 0,
            "confidence_pct": None,
            "expected_otif_pct": None,
            "note": "Plan has no scheduled stops to simulate.",
            "fragile_stops": [],
        }

    late_counts: dict[str, int] = {}
    finish_samples: list[float] = []
    otif_samples: list[float] = []
    fully_ontime_runs = 0
    reliable_runs = 0  # runs whose OTIF met the target

    def _thresh_for(stop: dict[str, Any]) -> Optional[int]:
        window = (stop.get("constraints") or {}).get("time_window")
        if window:
            win_end = _minutes(window[1])
            if win_end is not None:
                return win_end
        planned = _minutes(stop.get("etd"))  # builder stores arrival in 'etd'
        return planned + grace_minutes if planned is not None else None

    for _ in range(runs):
        run_late = 0
        run_total = 0
        day_finish = 0.0
        for truck_label, stops, depart, return_leg in routes:
            clock = float(depart)
            for s in stops:
                travel = float(s.get("travel_min") or 0)
                service = float(s.get("service_min") or 0)
                clock += travel * rng.lognormvariate(0.0, travel_sigma)
                if rng.random() < disruption_prob:
                    clock += rng.uniform(*disruption_extra_min)
                arrival = clock
                clock += service * rng.lognormvariate(0.0, service_sigma)

                run_total += 1
                key = f"{truck_label} → {s.get('client')}"
                late_counts.setdefault(key, 0)
                thresh = _thresh_for(s)
                if thresh is not None and arrival > thresh:
                    run_late += 1
                    late_counts[key] += 1
            clock += return_leg * rng.lognormvariate(0.0, travel_sigma)
            day_finish = max(day_finish, clock)

        run_otif = 100.0 * (run_total - run_late) / run_total if run_total else 100.0
        otif_samples.append(run_otif)
        finish_samples.append(day_finish)
        if run_late == 0:
            fully_ontime_runs += 1
        if run_otif >= otif_target:
            reliable_runs += 1

    finish_samples.sort()
    otif_samples.sort()

    fragile = sorted(
        ({"stop": k, "late_runs": v, "late_pct": round(100.0 * v / runs, 1)} for k, v in late_counts.items()),
        key=lambda d: d["late_runs"],
        reverse=True,
    )

    mean_otif = round(sum(otif_samples) / len(otif_samples), 1) if otif_samples else None

    return {
        "runs": runs,
        # Headline: how reliable the plan is (share of days meeting the OTIF
        # target) and the service level you can expect on a typical day.
        "confidence_pct": round(100.0 * reliable_runs / runs, 1),
        "expected_otif_pct": mean_otif,
        "otif_target_pct": otif_target,
        "all_ontime_pct": round(100.0 * fully_ontime_runs / runs, 1),
        "finish_p50": _clock(_percentile(finish_samples, 50)),
        "finish_p90": _clock(_percentile(finish_samples, 90)),
        "finish_worst": _clock(finish_samples[-1] if finish_samples else None),
        "otif_p10_pct": round(_percentile(otif_samples, 10), 1) if otif_samples else None,
        "stops_simulated": total_stops,
        "fragile_stops": fragile[:5],
        "model": {
            "travel_sigma": travel_sigma,
            "service_sigma": service_sigma,
            "disruption_prob": disruption_prob,
            "disruption_extra_min": list(disruption_extra_min),
            "grace_minutes": grace_minutes,
            "otif_target": otif_target,
            "seed": seed,
        },
    }
