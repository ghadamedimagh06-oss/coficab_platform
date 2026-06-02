from datetime import date, time
from hashlib import sha256
from pathlib import Path

from openpyxl import load_workbook
import pytest

from app.services.daily_plan_builder import DailyPlanBuilder
from app.services.excel_exporter import export_plan_to_xlsx


ROOT = Path(__file__).resolve().parents[2]
WEEKLY_DIR = ROOT / "weekly planning"
SOURCE_FILE = WEEKLY_DIR / "Weekly Delivery planning W0526.xlsx"


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    yield


def _first_assigned_stop(plan):
    for truck in plan["trucks"]:
        for trip in truck["trips"]:
            if trip["stops"]:
                return trip["stops"][0], trip
    raise AssertionError("generated plan has no assigned stops")


def test_daily_plan_builder_assigns_real_workbook_rows():
    plan = DailyPlanBuilder(WEEKLY_DIR).build(date(2026, 5, 26))

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


def test_export_round_trip_preserves_source_and_writes_edited_rows(tmp_path):
    source_hash = sha256(SOURCE_FILE.read_bytes()).hexdigest()
    plan = DailyPlanBuilder(WEEKLY_DIR).build(date(2026, 5, 26))
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
