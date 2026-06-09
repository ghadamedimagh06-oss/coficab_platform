from datetime import date, time
from hashlib import sha256
from pathlib import Path

from openpyxl import load_workbook
import pytest

from app.services.daily_plan_builder import DailyPlanBuilder
from app.services.excel_exporter import export_plan_to_xlsx
from app.services.osrm_service import OSRMTable


ROOT = Path(__file__).resolve().parents[2]
WEEKLY_DIR = ROOT / "weekly planning"
SOURCE_FILE = WEEKLY_DIR / "Weekly Delivery planning W0526.xlsx"


class FakeOSRM:
    @staticmethod
    def _meters(a, b):
        # Deterministic local stand-in for OSRM in tests.
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 * 111_000 * 1.3

    def table(self, coordinates):
        distances = []
        durations = []
        for a in coordinates:
            dist_row = []
            dur_row = []
            for b in coordinates:
                meters = self._meters(a, b)
                dist_row.append(meters)
                dur_row.append(meters / 1000 / 55 * 3600)
            distances.append(dist_row)
            durations.append(dur_row)
        return OSRMTable(durations_sec=durations, distances_m=distances)

    def route(self, coordinates):
        legs = []
        total_m = 0.0
        total_s = 0.0
        for a, b in zip(coordinates, coordinates[1:]):
            meters = self._meters(a, b)
            seconds = meters / 1000 / 55 * 3600
            total_m += meters
            total_s += seconds
            legs.append({
                "distance_m": meters,
                "distance_km": round(meters / 1000, 3),
                "duration_sec": seconds,
                "travel_min": int(round(seconds / 60)),
                "steps": [],
            })
        return {
            "distance_m": total_m,
            "total_distance_km": round(total_m / 1000, 3),
            "duration_sec": total_s,
            "total_travel_min": int(round(total_s / 60)),
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in coordinates]},
            "legs": legs,
        }


def _builder():
    return DailyPlanBuilder(WEEKLY_DIR, osrm=FakeOSRM())


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    yield


def _first_assigned_stop(plan):
    for truck in plan["trucks"]:
        for trip in truck["trips"]:
            if trip["stops"]:
                return trip["stops"][0], trip
    raise AssertionError("generated plan has no assigned stops")


def _minutes(value):
    hours, minutes = str(value).split(":")[:2]
    return int(hours) * 60 + int(minutes)


def test_daily_plan_builder_assigns_real_workbook_rows():
    plan = _builder().build(date(2026, 5, 26))

    assigned_count = sum(
        len(trip["stops"])
        for truck in plan["trucks"]
        for trip in truck["trips"]
    )

    assert plan["source_file"] == SOURCE_FILE.name
    assert plan["day"] == "2026-05-26"
    assert plan["summary"]["selected_delivery_rows"] > 0
    assert assigned_count > 0
    assert assigned_count + len(plan["unassigned"]) == plan["summary"]["deliveries_considered"]


def test_daily_plan_builder_does_not_parallelize_one_truck():
    plan = _builder().build(date(2026, 5, 26))

    for truck in plan["trucks"]:
        previous_trip_return = None
        for trip in truck["trips"]:
            depart = _minutes(trip["depart_at"])
            returned = _minutes(trip["return_at"])
            assert depart < returned
            if previous_trip_return is not None:
                assert depart >= previous_trip_return
            previous_trip_return = returned

            previous_stop_end = None
            for stop in trip["stops"]:
                start = _minutes(stop["etd"])
                end = _minutes(stop["eta"])
                assert start < end
                if previous_stop_end is not None:
                    assert start >= previous_stop_end
                previous_stop_end = end


def test_no_trip_exceeds_truck_capacity_or_working_hours():
    """Every trip must fit its truck by BOTH positions and gross weight, and
    return to the depot before the working day ends. Guards the kg-capacity
    enforcement and the rescue pass against regressions."""
    work_end = 20 * 60  # 20:00, matches DailyPlanConfig.work_end

    for day in (date(2026, 5, 25), date(2026, 5, 26), date(2026, 5, 28)):
        plan = _builder().build(day)
        by_id = {t["truck_id"]: t for t in plan["trucks"]}

        for truck in plan["trucks"]:
            for trip in truck["trips"]:
                load_pos = sum(float(s.get("quantity_positions") or 0) for s in trip["stops"])
                load_kg = sum(float(s.get("quantity_kg") or 0) for s in trip["stops"])
                assert load_pos <= truck["capacity_positions"], (
                    f"{day} truck {truck['truck_id']} trip {trip['trip_id']} "
                    f"overloaded: {load_pos} > {truck['capacity_positions']} positions"
                )
                assert load_kg <= truck["capacity_kg"] + 0.5, (
                    f"{day} truck {truck['truck_id']} trip {trip['trip_id']} "
                    f"overweight: {load_kg} > {truck['capacity_kg']} kg"
                )
                assert _minutes(trip["return_at"]) <= work_end, (
                    f"{day} truck {truck['truck_id']} trip {trip['trip_id']} "
                    f"returns after the working day ({trip['return_at']})"
                )

        # The hired truck (id 999) is a last resort: it must never carry load
        # while an owned truck of equal-or-greater capacity sits completely idle.
        rented = by_id.get(999)
        if rented and rented["trips"]:
            idle_owned = [
                t for t in plan["trucks"]
                if t["truck_id"] != 999 and not t["trips"]
                and t["capacity_positions"] >= rented["capacity_positions"]
            ]
            assert not idle_owned, (
                f"{day}: rented truck used while owned truck(s) "
                f"{[t['truck_id'] for t in idle_owned]} of equal capacity sat idle"
            )


def test_export_round_trip_preserves_source_and_writes_edited_rows(tmp_path):
    source_hash = sha256(SOURCE_FILE.read_bytes()).hexdigest()
    plan = _builder().build(date(2026, 5, 26))
    edited_stop, trip = _first_assigned_stop(plan)
    edited_row = edited_stop["raw"]["excel_row_index"]

    edited_stop["etd"] = "10:15"
    edited_stop["eta"] = "10:45"
    edited_stop["status"] = "cancelled"
    trip["stops"].append({
        "id": "new-test",
        "client": "New Export Client",
        "quantity_positions": 2,
        "position_count": 2,
        "quantity_kg": 1234,
        "etd": "14:00",
        "eta": "14:30",
        "priority": "high",
        "status": "new",
        "constraints": {"required_date": plan["day"], "notes": "manual add"},
        "raw": {},
    })

    exported = export_plan_to_xlsx(SOURCE_FILE, plan, tmp_path)

    assert sha256(SOURCE_FILE.read_bytes()).hexdigest() == source_hash
    assert exported.name.startswith("Weekly Delivery planning W0526_edited_")

    workbook = load_workbook(exported, data_only=False)
    sheet = workbook["Planning"] if "Planning" in workbook.sheetnames else workbook.active

    assert sheet.cell(edited_row, 4).value == time(10, 15)
    assert sheet.cell(edited_row, 6).value == "cancelled"

    appended_row = sheet.max_row
    assert sheet.cell(appended_row, 1).value == "Tuesday"
    assert isinstance(sheet.cell(appended_row, 2).value, int)
    assert sheet.cell(appended_row, 3).value == "New Export Client"
    assert sheet.cell(appended_row, 4).value == time(14, 0)
    assert sheet.cell(appended_row, 5).value == 2
    assert sheet.cell(appended_row, 6).value == "new"
    assert sheet.cell(appended_row, 7).value == "manual add"
    assert sheet.cell(appended_row, 10).value == "high"
    assert sheet.cell(appended_row, 12).value == 1234
