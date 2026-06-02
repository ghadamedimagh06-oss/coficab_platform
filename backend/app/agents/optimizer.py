"""
Optimizer agent — APScheduler job that runs the VRPTW optimizer daily at 06:00.

Triggered by the scheduler (see agents/scheduler.py) and also called directly
from IngestionService after a successful Excel import.

The result is always a new PlanVersion(DRAFT); it never overwrites a validated plan.
"""

import logging
from datetime import date, timedelta

log = logging.getLogger(__name__)


def run(target_day: date | None = None) -> dict:
    """
    Run the DB-aware VRPTW optimizer for *target_day* (default: tomorrow).

    Reads Camion(DISPONIBLE), Chauffeur(ACTIF), and DemandeLocal(NOUVELLE)
    from the database, partitions deliveries into geographic zones (one per
    available truck), solves each zone's route independently, and writes a
    DRAFT PlanVersion to the database.

    Returns a summary dict for logging / health-check purposes.
    """
    from app.database import SessionLocal
    from app.services.vrptw_optimizer import VrptwOptimizer, OptimizerConfig

    if not SessionLocal:
        log.warning("optimizer.run: database not available — skipping")
        return {"status": "skipped", "reason": "no database"}

    plan_day = target_day or (date.today() + timedelta(days=1))
    log.info("optimizer.run: starting for %s", plan_day)

    db = SessionLocal()
    try:
        cfg = OptimizerConfig(time_limit_sec=60)
        optimizer = VrptwOptimizer(db=db, cfg=cfg)
        version = optimizer.plan(day=plan_day)
        log.info(
            "optimizer.run: created PlanVersion id=%d plan_id=%d for %s",
            version.id, version.plan_id, plan_day,
        )
        return {
            "status": "ok",
            "plan_version_id": version.id,
            "plan_id": version.plan_id,
            "day": str(plan_day),
        }
    except ValueError as exc:
        # No demandes or no trucks — not an error, just nothing to do
        log.info("optimizer.run: nothing to optimise for %s — %s", plan_day, exc)
        return {"status": "nothing_to_do", "day": str(plan_day), "reason": str(exc)}
    except Exception as exc:
        log.error("optimizer.run: failed for %s — %s", plan_day, exc, exc_info=True)
        return {"status": "error", "day": str(plan_day), "reason": str(exc)}
    finally:
        db.close()
