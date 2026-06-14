from datetime import date
from app.routes.optimization import _available_trucks_for_daily_plan, WEEKLY_DIR
from app.services.daily_plan_builder import DailyPlanBuilder, DailyPlanConfig
from app.services import dashboard_service as ds


def summarize(plan, label):
    ua = plan.get("unassigned", [])
    acc = ds._new_kpi_acc()
    ds._accumulate_kpis(plan, acc)
    dem = acc["demanded_pos"]
    otif = round(100 * acc["in_full_on_time_pos"] / dem, 1) if dem else None
    otd = round(100 * acc["on_time_pos"] / dem, 1) if dem else None
    used = [t.get("truck_label") for t in plan.get("trucks", []) if t.get("trips")]
    print(f"{label}: trucks_used={len(used)} unassigned={len(ua)} OTD={otd}% OTIF={otif}%")
    for u in ua:
        print("   unassigned:", u.get("client"), u.get("quantity_positions") or u.get("position_count"), "pos")


# Full fleet (what the dashboard uses offline)
b_full = DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=False), trucks=None)
plan_full = b_full.build(day=date(2026, 6, 12))
fleet = [
    {"truck_id": t.get("truck_id"), "truck_label": t.get("truck_label"),
     "capacity_positions": t.get("capacity_positions"), "capacity_kg": t.get("capacity_kg")}
    for t in plan_full.get("trucks", [])
]
print("full fleet trucks present in plan:", len(fleet))
summarize(plan_full, "FULL FLEET")

# Drop trucks one at a time to see when a client first goes unassigned
for drop in range(1, len(fleet)):
    reduced = fleet[:-drop] if drop < len(fleet) else fleet[:1]
    b = DailyPlanBuilder(WEEKLY_DIR, cfg=DailyPlanConfig(prefer_ortools=False), trucks=reduced)
    plan = b.build(day=date(2026, 6, 12))
    summarize(plan, f"DROP {drop} -> {len(reduced)} trucks")
    if plan.get("unassigned"):
        break
