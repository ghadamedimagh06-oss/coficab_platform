"""Generated daily planning builder.

Creates a truck-by-time plan from the weekly planning workbook without
requiring a live database. The DB/OR-Tools path can replace the greedy builder
later; this keeps the Skill 14 page useful in the current dev state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional

from app.services.planning_service import PlanningService


DEFAULT_TRUCKS = [
    {"truck_id": 1, "truck_label": "Truck 1", "capacity_positions": 14, "capacity_kg": 10_200},
    {"truck_id": 2, "truck_label": "Truck 2", "capacity_positions": 14, "capacity_kg": 10_230},
    {"truck_id": 3, "truck_label": "Truck 3", "capacity_positions": 14, "capacity_kg": 9_227},
    {"truck_id": 4, "truck_label": "Truck 4", "capacity_positions": 14, "capacity_kg": 9_200},
    {"truck_id": 5, "truck_label": "Truck 5", "capacity_positions": 24, "capacity_kg": 24_950},
    {"truck_id": 6, "truck_label": "Truck 6", "capacity_positions": 14, "capacity_kg": 7_650},
]

PRIORITY_WEIGHT = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


@dataclass
class DailyPlanConfig:
    work_start: str = "08:00"
    work_end: str = "17:00"
    service_minutes: int = 30
    break_minutes: int = 15


class DailyPlanBuilder:
    def __init__(self, source_dir: Path, cfg: Optional[DailyPlanConfig] = None):
        self.source_dir = source_dir
        self.cfg = cfg or DailyPlanConfig()

    def build(self, day: date, source_file: Optional[str] = None) -> dict[str, Any]:
        source_path = self._resolve_source_file(source_file)
        plan_data = PlanningService(db=None).parse_weekly_planning(str(source_path))
        rows, selection = self._filter_rows(plan_data["rows"], day)
        delivery_rows = [row for row in rows if row.get("client")]
        deliveries = [self._delivery_from_row(row, day) for row in delivery_rows]

        trucks = [
            {
                **truck,
                "trips": [],
                "_cursor": self._minutes(self.cfg.work_start),
                "_load_positions": 0,
            }
            for truck in DEFAULT_TRUCKS
        ]
        unassigned = []

        for delivery in sorted(deliveries, key=self._sort_key):
            placed = self._place_delivery(trucks, delivery)
            if not placed:
                rented = self._ensure_rented_truck(trucks)
                placed = self._place_delivery([rented], delivery)
            if not placed:
                unassigned.append(delivery)

        clean_trucks = []
        for truck in trucks:
            clean_trucks.append({
                "truck_id": truck["truck_id"],
                "truck_label": truck["truck_label"],
                "capacity_positions": truck["capacity_positions"],
                "capacity_kg": truck["capacity_kg"],
                "trips": truck["trips"],
            })

        return {
            "plan_id": int(datetime.utcnow().timestamp()),
            "day": day.isoformat(),
            "source_file": source_path.name,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "selection": selection,
            "summary": {
                "source_rows": len(plan_data["rows"]),
                "selected_rows": len(rows),
                "selected_delivery_rows": len(delivery_rows),
                "deliveries_considered": len(deliveries),
                "total_positions": int(sum(delivery.get("quantity_positions") or 0 for delivery in deliveries)),
                "total_gross_weight_kg": round(sum(delivery.get("quantity_kg") or 0 for delivery in deliveries), 2),
            },
            "trucks": clean_trucks,
            "unassigned": unassigned,
        }

    def _resolve_source_file(self, source_file: Optional[str]) -> Path:
        if source_file:
            path = (self.source_dir / source_file).resolve()
            if self.source_dir.resolve() not in path.parents and path != self.source_dir.resolve():
                raise ValueError("source_file must stay inside weekly planning")
            if not path.exists():
                raise FileNotFoundError(f"source file not found: {source_file}")
            return path

        files = sorted(
            self.source_dir.glob("*.xlsx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        files = [p for p in files if not p.name.startswith("~$")]
        if not files:
            raise FileNotFoundError("no weekly planning xlsx file found")
        return files[0]

    def _filter_rows(self, rows: list[dict[str, Any]], target_day: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        target_name = target_day.strftime("%A")
        matched = [
            row for row in rows
            if (row.get("delivery_date") and row["delivery_date"].date() == target_day)
            or row.get("delivery_day") == target_name
        ]
        if matched:
            return matched, {
                "requested_date": target_day.isoformat(),
                "requested_day": target_name,
                "matched_day": target_name,
                "fallback": False,
            }
        fallback_day = next((row.get("delivery_day") for row in rows if row.get("delivery_day")), None)
        fallback_rows = [row for row in rows if row.get("delivery_day") == fallback_day] if fallback_day else rows
        return fallback_rows, {
            "requested_date": target_day.isoformat(),
            "requested_day": target_name,
            "matched_day": fallback_day,
            "fallback": True,
        }

    def _delivery_from_row(self, row: dict[str, Any], target_day: date) -> dict[str, Any]:
        constraints = PlanningService.parse_constraints(row)
        etd = self._format_time(row.get("etd"))
        eta = self._format_time(row.get("eta"))
        if constraints.get("time_window"):
            etd, eta = constraints["time_window"]
        gross_weight = self._weight_from_row(row)
        positions = float(row.get("position_count") or row.get("quantity") or 0)
        return {
            "id": int(row.get("row_number") or 0),
            "client": row.get("client") or row.get("end_location") or "Unknown client",
            "start_location": row.get("start_location") or "COFICAB Megrine",
            "end_location": row.get("end_location") or row.get("client") or "Unknown destination",
            "quantity_positions": positions,
            "position_count": positions,
            "quantity_kg": gross_weight,
            "etd": etd,
            "eta": eta,
            "priority": row.get("priority") or "normal",
            "status": "planned",
            "constraints": {
                **constraints,
                "required_date": constraints.get("required_date") or target_day.isoformat(),
            },
            "raw": row,
        }

    @staticmethod
    def _weight_from_row(row: dict[str, Any]) -> float:
        for key in ("total_gross_weight_kg", "gross_weight_kg", "pallet_weight_kg"):
            value = row.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0

    def _place_delivery(self, trucks: list[dict[str, Any]], delivery: dict[str, Any]) -> bool:
        required_truck = delivery["constraints"].get("required_truck_id")
        for truck in trucks:
            if required_truck and truck["truck_id"] != required_truck:
                continue

            start = max(truck["_cursor"], self._window_start(delivery))
            end = max(start + self.cfg.service_minutes, self._window_end_hint(delivery, start))
            if end + 15 > self._minutes(self.cfg.work_end):
                continue
            if not self._fits_time_window(delivery, end):
                continue
            quantity_positions = float(delivery.get("quantity_positions") or 0)
            should_open_trip = False
            if truck["_load_positions"] + quantity_positions > truck["capacity_positions"]:
                truck["_cursor"] += self.cfg.break_minutes
                truck["_load_positions"] = 0
                should_open_trip = True
                start = max(truck["_cursor"], self._window_start(delivery))
                end = start + self.cfg.service_minutes
            if end + 15 > self._minutes(self.cfg.work_end):
                continue
            if not self._fits_time_window(delivery, end):
                continue
            if truck["_load_positions"] + quantity_positions > truck["capacity_positions"]:
                continue

            assigned = {**delivery, "etd": self._clock(start), "eta": self._clock(end)}
            if should_open_trip or not truck["trips"]:
                trip_index = len(truck["trips"]) + 1
                truck["trips"].append({
                    "trip_id": f"{truck['truck_id']}-{trip_index}",
                    "depart_at": self._clock(max(self._minutes(self.cfg.work_start), start - 15)),
                    "return_at": self._clock(end + 15),
                    "stops": [],
                })
            trip = truck["trips"][-1]
            trip["stops"].append(assigned)
            trip["depart_at"] = min(trip["depart_at"], self._clock(max(self._minutes(self.cfg.work_start), start - 15)))
            trip["return_at"] = self._clock(end + 15)
            truck["_cursor"] = end + self.cfg.break_minutes
            truck["_load_positions"] += quantity_positions
            return True
        return False

    def _ensure_rented_truck(self, trucks: list[dict[str, Any]]) -> dict[str, Any]:
        rented = next((truck for truck in trucks if truck["truck_id"] == 999), None)
        if rented:
            return rented
        rented = {
            "truck_id": 999,
            "truck_label": "Rented",
            "capacity_positions": 24,
            "capacity_kg": 24_000,
            "trips": [],
            "_cursor": self._minutes(self.cfg.work_start),
            "_load_positions": 0,
        }
        trucks.append(rented)
        return rented

    def _sort_key(self, delivery: dict[str, Any]) -> tuple[int, int, float]:
        return (
            PRIORITY_WEIGHT.get(delivery.get("priority", "normal"), 2),
            self._window_start(delivery),
            -float(delivery.get("quantity_positions") or 0),
        )

    def _window_start(self, delivery: dict[str, Any]) -> int:
        window = delivery.get("constraints", {}).get("time_window")
        return self._minutes(window[0]) if window else self._minutes(delivery.get("etd")) or self._minutes(self.cfg.work_start)

    def _window_end_hint(self, delivery: dict[str, Any], fallback_start: int) -> int:
        window = delivery.get("constraints", {}).get("time_window")
        if window:
            return fallback_start + self.cfg.service_minutes
        eta = self._minutes(delivery.get("eta"))
        return eta if eta else fallback_start + self.cfg.service_minutes

    def _fits_time_window(self, delivery: dict[str, Any], end: int) -> bool:
        window = delivery.get("constraints", {}).get("time_window")
        if not window:
            return True
        window_end = self._minutes(window[1])
        return window_end is None or end <= window_end

    @staticmethod
    def _format_time(value: Any) -> Optional[str]:
        minutes = DailyPlanBuilder._minutes(value)
        return DailyPlanBuilder._clock(minutes) if minutes is not None else None

    @staticmethod
    def _minutes(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.hour * 60 + value.minute
        if isinstance(value, time):
            return value.hour * 60 + value.minute
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.hour * 60 + parsed.minute
            except ValueError:
                pass
        try:
            numeric = int(float(text))
            if 0 <= numeric < 24:
                return numeric * 60
            if 0 <= numeric < 2400:
                return (numeric // 100) * 60 + numeric % 100
        except ValueError:
            return None
        return None

    @staticmethod
    def _clock(minutes: int) -> str:
        minutes = max(0, min(minutes, 23 * 60 + 59))
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
