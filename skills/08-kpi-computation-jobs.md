# 08 — KPI Computation Jobs

> Goal: aggregate raw operational rows into `kpi_journalier` (daily) and `kpi_mensuel` (monthly) snapshots so the dashboard reads pre-computed numbers instead of re-aggregating on every request.

## Current implementation status

Audited and implemented on 2026-06-02:
- ✅ `backend/app/agents/kpi_jobs.py` runs daily, monthly, and range recompute snapshot upserts.
- ✅ `backend/app/agents/scheduler.py` schedules `kpi_daily` at 23:30 and `kpi_monthly` on day 1 at 02:00.
- ✅ `/api/metrics/kpi/snapshot/daily`, `/api/metrics/kpi/snapshot/monthly`, and `/api/metrics/kpi/recompute` are wired.
- ✅ `backend/scripts/recompute_kpis.py` provides the manual back-fill CLI.
- ✅ `backend/tests/test_kpi_jobs.py` verifies daily/monthly upserts and duplicate-safe reruns.

## KPI anchor
This skill is the **producer** of every number the dashboard renders. If the job is broken, the dashboard lies. If the job is correct, every KPI in skill 01 has a fresh row each day and each month.

---

## Jobs to run

| Job              | Frequency             | Reads from                                  | Writes to        |
|------------------|------------------------|---------------------------------------------|------------------|
| `kpi_daily`      | every day 23:30 local | `plan_mission`, `mission_demande`, `demandes_local`, `evenement_alea` | `kpi_journalier` |
| `kpi_monthly`    | day 1, 02:00 local    | `kpi_journalier` aggregated over the prior month | `kpi_mensuel`    |
| `kpi_recompute`  | on-demand (CLI/API)   | same as above, for an arbitrary range       | both             |

Use APScheduler (same scheduler that runs the other "agents" — see skill 00).

---

## Service: `backend/app/agents/kpi_jobs.py`

```python
import logging
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.kpi_service import KpiService
from app.models.kpi import KpiDefinition, KpiJournalier, KpiMensuel

log = logging.getLogger(__name__)

DAILY_CODES   = ["R4-06", "R4-02", "R4-13", "R4"]
MONTHLY_CODES = ["R4-02-PF", "R4-03", "R5-10", "R4-12"]

def run_daily(target: date | None = None) -> int:
    target = target or (date.today() - timedelta(days=1))
    db: Session = SessionLocal()
    try:
        ks = KpiService(db)
        n = 0
        for code in DAILY_CODES:
            compute_one_day(db, ks, code, target)
            n += 1
        # Monthly codes get an "in-progress" daily snapshot too,
        # so the dashboard's current-month tile isn't stale until day 1.
        for code in MONTHLY_CODES:
            compute_one_day(db, ks, code, target)
            n += 1
        db.commit()
        log.info("kpi_daily complete: %d snapshots for %s", n, target)
        return n
    finally:
        db.close()

def compute_one_day(db, ks: KpiService, code: str, day: date):
    definition = db.query(KpiDefinition).filter(KpiDefinition.code == code).first()
    if not definition:
        log.warning("kpi_definition missing code=%s — skip", code); return
    if   code == "R4-06":   r = ks.compute_otif(day)
    elif code == "R4-02":   r = ks.compute_otd(day)
    elif code == "R4-13":   r = ks.compute_fuel_efficiency(day)
    elif code == "R4":      r = ks.compute_load_efficiency(day)
    elif code == "R4-02-PF":r = ks.compute_premium_freight_eur(day)
    elif code == "R4-03":   r = ks.compute_premium_freight_count(day)
    elif code == "R5-10":   r = ks.compute_logistics_cost(date(day.year, day.month, 1))
    elif code == "R4-12":   r = ks.compute_customer_incidents(date(day.year, day.month, 1))
    else:                   return

    existing = (db.query(KpiJournalier)
                  .filter(KpiJournalier.kpi_def_id == definition.id,
                          KpiJournalier.date_mesure == day)
                  .first())
    if existing:
        existing.valeur = r.value; existing.color = r.color
    else:
        db.add(KpiJournalier(
            kpi_def_id=definition.id,
            date_mesure=day,
            valeur=r.value,
            color=r.color,
        ))

def run_monthly(year: int | None = None, month: int | None = None) -> int:
    today = date.today()
    prev_month_last_day = date(today.year, today.month, 1) - timedelta(days=1)
    year  = year  or prev_month_last_day.year
    month = month or prev_month_last_day.month

    db: Session = SessionLocal()
    try:
        ks = KpiService(db)
        n = 0
        for code in DAILY_CODES + MONTHLY_CODES:
            roll_up_month(db, ks, code, year, month)
            n += 1
        db.commit()
        log.info("kpi_monthly complete: %d snapshots for %04d-%02d", n, year, month)
        return n
    finally:
        db.close()

def roll_up_month(db, ks, code: str, year: int, month: int):
    definition = db.query(KpiDefinition).filter(KpiDefinition.code == code).first()
    if not definition: return

    # Monthly KPIs are recomputed from raw data (not from daily averages).
    first = date(year, month, 1)
    if code   == "R4-02-PF": r = ks.compute_premium_freight_eur(first)
    elif code == "R4-03":    r = ks.compute_premium_freight_count(first)
    elif code == "R5-10":    r = ks.compute_logistics_cost(first)
    elif code == "R4-12":    r = ks.compute_customer_incidents(first)
    else:                    r = ks.compute_month_average(definition.code, year, month)

    status = "OK" if r.color == "green" else "WARN" if r.color == "yellow" else "ALERT" if r.color == "red" else "NA"
    existing = (db.query(KpiMensuel)
                  .filter(KpiMensuel.kpi_def_id == definition.id,
                          KpiMensuel.annee == year, KpiMensuel.mois == month)
                  .first())
    if existing:
        existing.valeur = r.value; existing.color = r.color; existing.status = status
    else:
        db.add(KpiMensuel(
            kpi_def_id=definition.id, annee=year, mois=month,
            valeur=r.value, target=definition.target_2025,
            color=r.color, status=status,
        ))
```

Add `KpiService.compute_premium_freight_eur(day)`, `compute_premium_freight_count(day)`, `compute_month_average(code, year, month)` to skill 01's `KpiService` — straightforward extensions using the same query patterns.

---

## Scheduler wiring

`backend/app/agents/scheduler.py`:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from app.agents import kpi_jobs, collector, monitor, notifier

def start_scheduler():
    s = BackgroundScheduler(timezone="Europe/Paris")
    s.add_job(kpi_jobs.run_daily,   "cron", hour=23, minute=30, id="kpi_daily")
    s.add_job(kpi_jobs.run_monthly, "cron", day=1, hour=2,  minute=0, id="kpi_monthly")
    s.add_job(collector.run,        "interval", minutes=15, id="collector")
    s.add_job(monitor.run,          "interval", seconds=30, id="monitor")
    s.add_job(notifier.flush,       "interval", seconds=10, id="notifier_retry")
    s.start()
    return s
```

Called from `main.py` `lifespan`.

---

## CLI for manual back-fill

`backend/scripts/recompute_kpis.py`:

```python
import argparse, datetime as dt
from app.agents.kpi_jobs import run_daily, run_monthly

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", required=True)   # YYYY-MM-DD
    ap.add_argument("--to",   dest="to",  required=True)
    args = ap.parse_args()
    frm = dt.date.fromisoformat(args.frm); to = dt.date.fromisoformat(args.to)
    day = frm
    while day <= to:
        run_daily(day)
        day += dt.timedelta(days=1)
    # Roll up the months touched
    months = {(d.year, d.month) for d in
              (frm + dt.timedelta(days=i) for i in range((to - frm).days + 1))}
    for y, m in sorted(months):
        run_monthly(y, m)
```

Use after schema changes, formula tweaks, or backfilling historical data.

---

## API endpoints

```
GET /api/metrics/kpi                          all KPIs for today, dashboard payload
GET /api/metrics/kpi/{code}?period=monthly    history for one KPI
GET /api/metrics/kpi/snapshot/daily?date=     all KPI values for one day
GET /api/metrics/kpi/snapshot/monthly?ym=     all KPI values for one month
POST /api/metrics/kpi/recompute               (admin) body: { from, to }
```

The **dashboard payload** is shaped to match the existing `frontend/data/dashboardData.ts` exactly so the swap is one-liner (see skill 09):

```json
{
  "kpis": [
    { "code": "R4-06", "label": "OTIF",         "value": 92.54, "unit": "%",       "color": "yellow", "target": 96,   "trend": -1.2 },
    { "code": "R4-02", "label": "OTD",          "value": 93.57, "unit": "%",       "color": "yellow", "target": 96,   "trend": 0.8 },
    { "code": "R4-13", "label": "Fuel Eff.",    "value": 0.15,  "unit": "mL/T.km", "color": "green",  "target": 0.14, "trend": -0.01 },
    { "code": "R5-10", "label": "Logistics €/T","value": 17.1,  "unit": "€/T",     "color": "green",  "target": 16,   "trend": -0.4 },
    { "code": "R4",    "label": "Load Eff.",    "value": 74,    "unit": "%",       "color": "yellow", "target": 80,   "trend": 1.5 }
  ]
}
```

---

## Anti-patterns

- ❌ Computing KPIs on dashboard read. Latency goes up, formulas diverge.
- ❌ Storing daily averages and then "averaging the averages" for monthly. **Monthly = raw aggregate over the month**, computed from primary data (see `roll_up_month`).
- ❌ Forgetting to UPSERT — a re-run on the same date must not insert a duplicate row.
- ❌ Hardcoding color thresholds in the job. Read from `kpi_definition`.

---

## Verification

1. Seed a known dataset: 10 missions for `2026-05-20`, 8 on-time, 2 late by 30 min.
2. Run `run_daily(date(2026,5,20))` manually.
3. Check `kpi_journalier`: row exists for each code, `R4-02` value ≈ 80% (depending on quantity weighting).
4. Repeat for the whole month (use the back-fill CLI).
5. `run_monthly(2026, 5)` → `kpi_mensuel` rows populated; `status` matches `color`.
6. Hit `/api/metrics/kpi` → JSON matches the schema above, dashboard renders without errors.
