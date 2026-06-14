"""Agentic copilot write-tools (W3.1).

Turns a plain-language instruction into a concrete, grounded PROPOSAL the
dispatcher can approve — without depending on the LLM. A deterministic intent
parser maps the message to one of a few actions and executes it against the
current plan:

  • summary   — a grounded read-out of the live plan (trucks, coverage, km, CO₂,
                cost, finish);
  • explain   — why a given truck's route looks the way it does (reuses the
                explainable-routing engine);
  • replan    — "truck N broke down": re-optimise the remaining stops on the
                remaining fleet and return the recovery + a diff for one-click
                approval (a WRITE action: the proposal carries the new plan).

This is the safe, testable core. When the Groq/Llama copilot is configured it can
call these as tools; when it is not, the same actions work from typed commands,
so the feature degrades gracefully. Nothing is applied server-side — the caller
approves a proposal and applies the returned plan.
"""

from __future__ import annotations

import re
from typing import Any, Optional


# ───────────────────────────────────────────────────────────── intent parser
_TRUCK_RE = re.compile(r"\btruck\s*#?\s*(\d+)\b", re.I)
_BARE_NUM_RE = re.compile(r"#?(\d+)")


def _truck_ids(text: str) -> list[int]:
    """Truck numbers mentioned, preferring the explicit 'truck N' form and
    falling back to any bare numbers (so 'break down 3 and 5' still works)."""
    ids = [int(m) for m in _TRUCK_RE.findall(text)]
    if not ids:
        ids = [int(m) for m in _BARE_NUM_RE.findall(text)]
    # de-dupe, preserve order
    seen: list[int] = []
    for i in ids:
        if i not in seen:
            seen.append(i)
    return seen


def interpret(text: str) -> dict[str, Any]:
    """Map a free-text instruction to a structured intent. Deterministic — no LLM.

    Returns {"action": <name>, ...params}. Unknown text returns action="unknown"
    (with the original text) so the caller can fall back to the chat model."""
    t = (text or "").strip().lower()
    if not t:
        return {"action": "unknown", "text": text}

    if re.search(r"\b(help|what can you (do|help)|commands?|how do i)\b", t):
        return {"action": "help"}

    # Disruption / recovery (a WRITE action). Recognised before "explain" so
    # "truck 3 broke down, replan" isn't mistaken for an explain.
    if re.search(r"\b(broke|broken|break ?down|breaks? down|out of service|disrupt\w*|recover\w*|re-?plan)\b", t):
        ids = _truck_ids(t)
        return {"action": "replan", "truck_ids": ids}

    if re.search(r"\b(explain|why|rationale|reason)\b", t) and ("truck" in t or _BARE_NUM_RE.search(t)):
        ids = _truck_ids(t)
        return {"action": "explain", "truck_id": ids[0] if ids else None}

    if re.search(r"\b(summar\w*|overview|status|recap|how('?s| is) the plan|where do we stand)\b", t):
        return {"action": "summary"}

    return {"action": "unknown", "text": text}


# ─────────────────────────────────────────────────────── deterministic summary
def _finish_minutes(plan: dict[str, Any]) -> int:
    latest = 0
    for tk in plan.get("trucks", []):
        for trip in tk.get("trips", []):
            try:
                hh, mm = str(trip.get("return_at")).split(":")[:2]
                latest = max(latest, int(hh) * 60 + int(mm))
            except (ValueError, AttributeError):
                continue
    return latest


def _clock(minutes: int) -> str:
    m = max(0, int(minutes))
    return f"{m // 60:02d}:{m % 60:02d}"


# Hard (non-recoverable) unassigned reasons, mirroring DailyPlanBuilder.
_HARD_DROP_MARKERS = ("export", "could not locate", "exceeds the largest truck", "cubes out", "no available trucks")


def plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    """A grounded summary of the live plan — all figures read straight off the
    plan, nothing invented."""
    trucks = plan.get("trucks", [])
    used = [t for t in trucks if t.get("trips")]
    trips = sum(len(t.get("trips", [])) for t in used)
    stops = sum(len(trip.get("stops", [])) for t in used for trip in t.get("trips", []))

    unassigned = plan.get("unassigned", [])
    hard = [u for u in unassigned if any(m in str(u.get("unassigned_reason") or "").lower() for m in _HARD_DROP_MARKERS)]
    recoverable = [u for u in unassigned if u not in hard]

    sustain = plan.get("sustainability") or {}
    cost = (plan.get("estimated_cost_tnd") or {}).get("total")
    finish = _finish_minutes(plan)

    lines = [
        f"{len(used)} trucks running {trips} trips, {stops} stops delivered.",
    ]
    if recoverable:
        lines.append(f"⚠ {len(recoverable)} serviceable drop(s) not yet placed.")
    if hard:
        lines.append(f"{len(hard)} can't be served by truck (export/oversize/ungeocoded).")
    if sustain.get("planned_distance_km") is not None:
        lines.append(f"{sustain['planned_distance_km']:.0f} km · {sustain.get('co2_kg', 0):.0f} kg CO₂.")
    if cost is not None:
        lines.append(f"Estimated cost {cost:.0f} TND.")
    if finish:
        lines.append(f"Last truck home by {_clock(finish)}.")

    return {
        "action": "summary",
        "title": "Plan summary",
        "trucks_used": len(used),
        "trips": trips,
        "stops_delivered": stops,
        "unassigned_recoverable": len(recoverable),
        "unassigned_hard": len(hard),
        "distance_km": sustain.get("planned_distance_km"),
        "co2_kg": sustain.get("co2_kg"),
        "cost_tnd": cost,
        "finish": _clock(finish) if finish else None,
        "summary": " ".join(lines),
        "applies": False,
    }


def help_text() -> dict[str, Any]:
    return {
        "action": "help",
        "title": "What Optiroute can do",
        "summary": (
            "Try: “summary” for a plan read-out · “explain truck 5” for why a route "
            "looks the way it does · “truck 3 broke down, replan” to simulate a "
            "breakdown and propose a recovery you can apply with one click."
        ),
        "applies": False,
    }
