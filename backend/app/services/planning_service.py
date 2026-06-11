"""Planning Service for CofICab Platform

Handles weekly Excel planning ingestion, validated-planning comparison,
J+1 change detection, review operations, and audit history tracking.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import unicodedata

import pandas as pd
from sqlalchemy.orm import Session

from app.models.planning_version import PlanningVersion
from app.models.planning_change_log import PlanningChangeLog
from app.models.planning_diff import PlanningDiff
from app.models.livraison import Livraison
from app.models.ingestion_log import IngestionLog

WEEKDAY_REVERSE = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

J_PLUS_1_MAPPING = {
    "Monday": "Tuesday",
    "Tuesday": "Wednesday",
    "Wednesday": "Thursday",
    "Thursday": "Friday",
    "Friday": "Saturday",
}

DAY_NAMES = {
    "mon": "Monday",
    "monday": "Monday",
    "tue": "Tuesday",
    "tues": "Tuesday",
    "tuesday": "Tuesday",
    "wed": "Wednesday",
    "wednesday": "Wednesday",
    "thu": "Thursday",
    "thurs": "Thursday",
    "thursday": "Thursday",
    "fri": "Friday",
    "friday": "Friday",
    "sat": "Saturday",
    "saturday": "Saturday",
    "sun": "Sunday",
    "sunday": "Sunday",
}

VALID_FIELDS = [
    "driver",
    "vehicle",
    "start_location",
    "end_location",
    "distance_km",
    "status",
    "priority",
    "notes",
    "client",
    "etd",
    "eta",
    "quantity",
]

AUDIT_SOURCE_WATCHDOG = "WATCHDOG_SYSTEM"
AUDIT_SOURCE_USER = "USER"
AUDIT_TYPE_EXCEL_SYNC = "EXCEL_SYNC"
AUDIT_TYPE_MANUAL_UPDATE = "MANUAL_UPDATE"
AUDIT_TYPE_REVALIDATION = "REVALIDATION"


class PlanningService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def parse_constraints(row: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Skill 14 delivery constraints from a parsed Excel row."""
        constraints: Dict[str, Any] = {}

        etd = PlanningService._constraint_time(row.get("etd"))
        eta = PlanningService._constraint_time(row.get("eta"))
        if etd and eta:
            constraints["time_window"] = [etd, eta]

        vehicle = str(row.get("vehicle") or "").strip()
        if vehicle:
            digits = "".join(ch for ch in vehicle if ch.isdigit())
            if digits:
                constraints["required_truck_id"] = int(digits)
            constraints["required_vehicle"] = vehicle

        driver = str(row.get("driver") or "").strip()
        if driver:
            constraints["required_driver"] = driver

        delivery_date = row.get("delivery_date")
        if delivery_date is not None and not pd.isna(delivery_date):
            try:
                if hasattr(delivery_date, "date"):
                    constraints["required_date"] = delivery_date.date().isoformat()
                else:
                    constraints["required_date"] = pd.to_datetime(delivery_date).date().isoformat()
            except Exception:
                pass

        notes = str(row.get("notes") or "").strip()
        if notes:
            constraints["notes"] = notes
            constraints["comment_constraint"] = notes
            lowered = PlanningService._strip_accents(notes.lower()).replace("’", "'")
            if "apres-midi" in lowered or "apres midi" in lowered or "apresmidi" in lowered:
                constraints["time_window"] = ["13:00", "17:00"]
            client_hour = PlanningService._hour_from_comment(lowered, ("chez le client", "client"))
            if client_hour:
                constraints["time_window"] = [client_hour, PlanningService._add_minutes(client_hour, 60)]
            approximate_hour = PlanningService._hour_from_comment(lowered, ("vers",))
            if approximate_hour:
                constraints["time_window"] = [approximate_hour, PlanningService._add_minutes(approximate_hour, 60)]
            departure_hour = PlanningService._hour_from_comment(lowered, ("depart",))
            if departure_hour:
                constraints["required_departure"] = departure_hour
            if "urgent" in lowered:
                constraints["priority_hint"] = "urgent"

        return constraints

    @staticmethod
    def _constraint_time(value: Any) -> Optional[str]:
        if value is None or pd.isna(value):
            return None
        if hasattr(value, "hour") and hasattr(value, "minute"):
            return f"{value.hour:02d}:{value.minute:02d}"
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.strftime("%H:%M")
            except ValueError:
                pass
        try:
            numeric = int(float(text))
            if 0 <= numeric < 24:
                return f"{numeric:02d}:00"
            if 0 <= numeric < 2400:
                return f"{numeric // 100:02d}:{numeric % 100:02d}"
        except ValueError:
            return None
        return None

    @staticmethod
    def _strip_accents(value: str) -> str:
        return "".join(
            char for char in unicodedata.normalize("NFKD", value)
            if not unicodedata.combining(char)
        )

    @staticmethod
    def _hour_from_comment(text: str, keywords: Tuple[str, ...]) -> Optional[str]:
        import re

        if not any(keyword in text for keyword in keywords):
            return None
        match = re.search(r"\b([01]?\d|2[0-3])\s*h\s*([0-5]\d)?\b", text)
        if not match:
            return None
        return f"{int(match.group(1)):02d}:{int(match.group(2) or 0):02d}"

    @staticmethod
    def _add_minutes(clock: str, minutes: int) -> str:
        parsed = datetime.strptime(clock, "%H:%M")
        shifted = parsed + timedelta(minutes=minutes)
        return shifted.strftime("%H:%M")

    @staticmethod
    def _excel_time(value: Any) -> Optional[str]:
        parsed = PlanningService._constraint_time(value)
        if parsed:
            return parsed
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        if value is None or pd.isna(value) or str(value).strip() == "":
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _integer(value: Any) -> Optional[int]:
        number = PlanningService._number(value)
        if number is None:
            return None
        return int(number)

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    def _normalize_weekday(self, raw_value: Any) -> Optional[str]:
        if raw_value is None or pd.isna(raw_value):
            return None
        value = str(raw_value).strip().lower()
        if value in DAY_NAMES:
            return DAY_NAMES[value]
        if value[:3] in DAY_NAMES:
            return DAY_NAMES[value[:3]]
        return None

    def _next_j_plus_1_day(self, today: Optional[date] = None) -> Optional[str]:
        current = today or date.today()
        weekday_name = WEEKDAY_REVERSE[current.weekday()]
        return J_PLUS_1_MAPPING.get(weekday_name)

    def _infer_delivery_day(self, df: pd.DataFrame) -> List[Optional[str]]:
        candidate_columns = [c for c in df.columns if str(c).strip().lower() in ("day", "weekday", "delivery_day", "delivery day", "jour")]
        if candidate_columns:
            day_col = candidate_columns[0]
            inferred = []
            current_day = None
            for value in df[day_col].tolist():
                normalized = self._normalize_weekday(value)
                if normalized:
                    current_day = normalized
                inferred.append(current_day)
            return inferred

        first_col = df.columns[0]
        values = df[first_col].tolist()
        inferred = []
        current_day = None
        for cell in values:
            normalized = self._normalize_weekday(cell)
            if normalized:
                current_day = normalized
                inferred.append(None)
                continue
            inferred.append(current_day)

        if any(inferred):
            return inferred

        date_columns = [c for c in df.columns if str(c).strip().lower() in ("delivery_date", "date", "scheduled_date")]
        if date_columns:
            date_col = date_columns[0]
            inferred = []
            for value in df[date_col].tolist():
                if pd.isna(value):
                    inferred.append(None)
                else:
                    try:
                        inferred.append(pd.to_datetime(value).strftime("%A"))
                    except Exception:
                        inferred.append(None)
            return inferred

        return [None] * len(df)

    def _compute_week(self, rows: List[Dict[str, Any]]) -> date:
        dates = [row["delivery_date"] for row in rows if row.get("delivery_date")]
        if dates:
            min_date = min(dates)
            return min_date - timedelta(days=min_date.weekday())
        return date.today() - timedelta(days=date.today().weekday())

    def _normalize_column_name(self, column_name: Any) -> Optional[str]:
        if column_name is None or pd.isna(column_name):
            return None
        normalized = str(column_name).strip().lower()
        normalized = normalized.replace("\xa0", " ")
        normalized = normalized.replace("-", " ").replace(".", " ")
        normalized = "_".join(normalized.split())
        return normalized

    def _read_planning_dataframe(self, file_path: str) -> pd.DataFrame:
        candidates = [
            {"sheet_name": "Planning", "header": 2},
            {"sheet_name": "Planning", "header": 0},
            {"header": 2},
            {"header": 0},
        ]
        last_error = None
        for kwargs in candidates:
            try:
                df = pd.read_excel(file_path, **kwargs)
                if not df.empty:
                    df.attrs["header_row"] = int(kwargs.get("header", 0)) + 1
                    return df
            except Exception as exc:
                last_error = exc
        raise ValueError(f"Failed to read Excel planning sheet: {last_error}")

    def parse_weekly_planning(self, file_path: str) -> Dict[str, Any]:
        df = self._read_planning_dataframe(file_path)
        if df.empty:
            raise ValueError("Excel file contains no planning rows")

        column_map = {
            "delivery_day": "delivery_day",
            "delivery day": "delivery_day",
            "jour": "delivery_day",
            "weekday": "delivery_day",
            "day": "delivery_day",
            "n°": "row_number",
            "n": "row_number",
            "no": "row_number",
            "customer": "client",
            "client": "client",
            "driver": "driver",
            "vehicle": "vehicle",
            "start": "start_location",
            "start_location": "start_location",
            "from": "start_location",
            "origin": "start_location",
            "end": "end_location",
            "end_location": "end_location",
            "to": "end_location",
            "destination": "end_location",
            "distance": "distance_km",
            "distance_km": "distance_km",
            "etd": "etd",
            "eta": "eta",
            "quantity": "quantity",
            "status": "status",
            "priority": "priority",
            "notes": "notes",
            "comments": "notes",
            "position": "quantity",
            "position_number": "quantity",
            "position_nbr": "quantity",
            "position_no": "quantity",
            "pallets": "quantity",
            "pallet_count": "quantity",
            "pallet_number": "quantity",
            "pallet_weight": "pallet_weight_kg",
            "gross_weight": "gross_weight_kg",
            "total_gross_weight": "total_gross_weight_kg",
        }

        rename_map = {}
        used_targets = set()
        for original in df.columns:
            normalized = self._normalize_column_name(original)
            if normalized is None:
                continue
            target = column_map.get(normalized, normalized)
            if target in used_targets:
                continue
            rename_map[original] = target
            used_targets.add(target)
        df = df.rename(columns=rename_map)

        weekday_values = self._infer_delivery_day(df)
        rows = []
        for index, row in df.iterrows():
            raw_delivery_day = row.get("delivery_day")
            delivery_day = self._normalize_weekday(raw_delivery_day)
            if delivery_day is None and index < len(weekday_values):
                delivery_day = weekday_values[index]

            row_number_value = row.get("row_number")
            if pd.isna(row_number_value) or str(row_number_value).strip() == "":
                row_number = int(index + 1)
            else:
                try:
                    row_number = int(row_number_value)
                except Exception:
                    row_number = int(index + 1)

            client = self._text(row.get("client"))
            driver = self._text(row.get("driver")) or ""
            vehicle = self._text(row.get("vehicle")) or ""
            start_location = self._text(row.get("start_location")) or ""
            end_location = self._text(row.get("end_location")) or ""
            if not start_location:
                start_location = "COFICAB Sidi Hassine"
            if not end_location:
                end_location = client or "Unknown destination"

            distance_km = self._number(row.get("distance_km", row.get("distance", 0))) or 0.0

            etd = self._excel_time(row.get("etd"))
            eta = self._excel_time(row.get("eta"))
            notes = self._text(row.get("notes"))

            raw_status = str(row.get("status", "pending")).strip() if not pd.isna(row.get("status", "pending")) else "pending"
            status = raw_status.lower().strip()
            if status in {"confirmed", "confirmed ", "ok", "scheduled", "planned", "valid"}:
                status = "pending"
            elif status in {"completed", "delivered", "done", "finished"}:
                status = "completed"
            elif status in {"in transit", "in_transit", "on route", "en route"}:
                status = "in_transit"
            elif status == "":
                status = "pending"
            elif status not in {"pending", "completed", "in_transit"}:
                status = "pending"

            priority = str(row.get("priority", "normal")).strip().lower() if not pd.isna(row.get("priority", "normal")) else "normal"
            if priority not in {"urgent", "high", "normal", "low"}:
                priority = "normal"

            quantity = self._integer(row.get("quantity"))
            pallet_weight_kg = self._number(row.get("pallet_weight_kg"))
            gross_weight_kg = self._number(row.get("gross_weight_kg"))
            total_gross_weight_kg = self._number(row.get("total_gross_weight_kg"))

            row_data = {
                "excel_row_index": int(index) + int(df.attrs.get("header_row", 1)) + 1,
                "row_number": row_number,
                "delivery_day": delivery_day,
                "driver": driver,
                "vehicle": vehicle,
                "start_location": start_location,
                "end_location": end_location,
                "distance_km": distance_km,
                "status": status,
                "priority": priority,
                "notes": notes,
                "client": client,
                "etd": etd,
                "eta": eta,
                "quantity": quantity,
                "position_count": quantity,
                "pallet_weight_kg": pallet_weight_kg,
                "gross_weight_kg": gross_weight_kg,
                "total_gross_weight_kg": total_gross_weight_kg,
                "delivery_date": None,
            }

            date_columns = [c for c in df.columns if str(c).strip().lower() in ("delivery_date", "date", "scheduled_date")]
            if date_columns:
                date_value = row.get(date_columns[0])
                if not pd.isna(date_value):
                    try:
                        row_data["delivery_date"] = pd.to_datetime(date_value)
                    except Exception:
                        row_data["delivery_date"] = None

            rows.append(row_data)

        week = self._compute_week(rows)
        return {
            "file_name": file_path.split("/")[-1].split("\\")[-1],
            "week": week,
            "rows": rows,
        }

    def _diff_value(self, old: Any, new: Any) -> bool:
        if old is None and new in (None, "", 0):
            return False
        if isinstance(old, float) and isinstance(new, float):
            return abs(old - new) > 1e-6
        return str(old).strip() != str(new).strip()

    def _calculate_impact(self, field_name: str, old_value: Any, new_value: Any) -> Dict[str, Any]:
        impact_eta = None
        impact_cost = None
        impact_risk = None

        if field_name in ("etd", "eta"):
            impact_eta = 60.0 if old_value and new_value and old_value != new_value else 0.0
            impact_risk = "Medium" if impact_eta else "Low"

        if field_name == "vehicle":
            impact_cost = 120.0
            impact_risk = "High"

        if field_name == "driver":
            impact_risk = "Medium"

        if field_name == "quantity":
            impact_cost = 80.0
            impact_risk = "Medium"

        if field_name == "status":
            impact_risk = "High" if new_value and new_value.lower() in ("delayed", "critical") else "Medium"

        return {
            "impact_eta": impact_eta,
            "impact_cost": impact_cost,
            "impact_risk": impact_risk,
        }

    def create_planning_from_excel(self, file_path: str, created_by: int) -> PlanningVersion:
        plan_data = self.parse_weekly_planning(file_path)
        week = plan_data["week"]
        file_name = plan_data["file_name"]
        rows = plan_data["rows"]

        existing_planning = self.db.query(PlanningVersion).filter(PlanningVersion.week == week).first()
        if existing_planning and existing_planning.status == "DRAFT":
            self.db.query(Livraison).filter(Livraison.planning_id == existing_planning.id).delete()
            planning = existing_planning
        else:
            planning = PlanningVersion(
                week=week,
                status="DRAFT",
                created_by=created_by,
                file_name=file_name,
                excel_path=file_path,
                source=AUDIT_SOURCE_WATCHDOG,
            )
            self.db.add(planning)
            self.db.commit()
            self.db.refresh(planning)

        livraison_objects = []
        for row in rows:
            if not any([
                row["client"],
                row["etd"],
                row["eta"],
                row["notes"],
                row["distance_km"] > 0,
            ]):
                continue

            driver = row["driver"] or ""
            vehicle = row["vehicle"] or ""
            start_location = row["start_location"] or "COFICAB Sidi Hassine"
            end_location = row["end_location"] or row["client"] or "Unknown destination"
            if row["distance_km"] is None:
                distance_km = 0.0
            else:
                distance_km = row["distance_km"]

            livraison = Livraison(
                planning_id=planning.id,
                delivery_day=row["delivery_day"],
                delivery_date=row["delivery_date"],
                row_number=row["row_number"],
                client=row["client"],
                etd=row["etd"],
                eta=row["eta"],
                quantity=row["quantity"],
                driver=driver,
                vehicle=vehicle,
                start_location=start_location,
                end_location=end_location,
                distance_km=distance_km,
                status=row["status"] or "pending",
                priority=row["priority"] or "normal",
                notes=row["notes"],
            )
            livraison_objects.append(livraison)

        if livraison_objects:
            self.db.add_all(livraison_objects)
            self.db.commit()

        return planning

    def _find_matching_delivery(self, planning: PlanningVersion, row: Dict[str, Any]) -> Optional[Livraison]:
        if row.get("row_number") is not None:
            candidate = self.db.query(Livraison).filter(
                Livraison.planning_id == planning.id,
                Livraison.row_number == row["row_number"],
                Livraison.delivery_day == row.get("delivery_day"),
            ).first()
            if candidate:
                return candidate

        return self.db.query(Livraison).filter(
            Livraison.planning_id == planning.id,
            Livraison.delivery_day == row.get("delivery_day"),
            Livraison.driver == row.get("driver"),
            Livraison.vehicle == row.get("vehicle"),
            Livraison.start_location == row.get("start_location"),
            Livraison.end_location == row.get("end_location"),
        ).first()

    def compare_validated_planning_with_excel(self, planning: PlanningVersion, file_path: str) -> Dict[str, Any]:
        if planning.status != "VALIDATED":
            raise ValueError("Planning version must be VALIDATED to compare Excel changes")

        plan_data = self.parse_weekly_planning(file_path)
        rows = plan_data["rows"]
        j_plus_1_day = self._next_j_plus_1_day()

        diffs = []
        ignored = []

        for row in rows:
            is_j_plus_1 = row.get("delivery_day") == j_plus_1_day
            matched = self._find_matching_delivery(planning, row)
            baseline = matched

            for field in VALID_FIELDS:
                old_value = getattr(baseline, field, None) if baseline else None
                new_value = row.get(field)
                if not self._diff_value(old_value, new_value):
                    continue

                impact = self._calculate_impact(field, old_value, new_value)
                diff_entry = {
                    "planning_id": planning.id,
                    "delivery_id": matched.id if matched else None,
                    "delivery_day": row.get("delivery_day"),
                    "row_number": row.get("row_number"),
                    "field_name": field,
                    "old_value": old_value,
                    "new_value": new_value,
                    "impact_eta": impact["impact_eta"],
                    "impact_cost": impact["impact_cost"],
                    "impact_risk": impact["impact_risk"],
                    "is_j_plus_1": bool(is_j_plus_1),
                    "ignored_reason": None if is_j_plus_1 else "outside_j_plus_1",
                }
                diffs.append(diff_entry)

                if is_j_plus_1 and baseline:
                    setattr(baseline, field, new_value)
                if is_j_plus_1 and not baseline:
                    new_delivery = Livraison(
                        planning_id=planning.id,
                        delivery_day=row.get("delivery_day"),
                        delivery_date=row.get("delivery_date"),
                        row_number=row.get("row_number"),
                        client=row.get("client"),
                        etd=row.get("etd"),
                        eta=row.get("eta"),
                        quantity=row.get("quantity"),
                        driver=row.get("driver", ""),
                        vehicle=row.get("vehicle", ""),
                        start_location=row.get("start_location", ""),
                        end_location=row.get("end_location", ""),
                        distance_km=row.get("distance_km") or 0.0,
                        status=row.get("status") or "pending",
                        priority=row.get("priority") or "normal",
                        notes=row.get("notes"),
                    )
                    self.db.add(new_delivery)
                    self.db.flush()
                    diff_entry["delivery_id"] = new_delivery.id
                    baseline = new_delivery

            if not is_j_plus_1 and any(d["row_number"] == row.get("row_number") and d["field_name"] for d in diffs):
                ignored.append(diff_entry)

        self.db.commit()

        if diffs:
            for diff in diffs:
                audit = PlanningChangeLog(
                    planning_id=planning.id,
                    timestamp=datetime.now(timezone.utc),
                    source=AUDIT_SOURCE_WATCHDOG,
                    modified_by=0,
                    field_name=diff["field_name"],
                    old_value=str(diff["old_value"]) if diff["old_value"] is not None else None,
                    new_value=str(diff["new_value"]) if diff["new_value"] is not None else None,
                    reason=f"Detected Excel sync change for J+1 day {diff['delivery_day']}",
                    change_type=AUDIT_TYPE_EXCEL_SYNC,
                    user_id=None,
                )
                self.db.add(audit)

            status_set = "PENDING_REVIEW" if any(d["is_j_plus_1"] for d in diffs) else "MODIFIED_AFTER_VALIDATION"
            planning.status = status_set
            planning.last_review_at = datetime.now(timezone.utc)
            self.db.add(planning)
            self.db.commit()

            for diff in diffs:
                planning_diff = PlanningDiff(
                    planning_id=planning.id,
                    delivery_id=diff["delivery_id"],
                    delivery_day=diff["delivery_day"],
                    row_number=diff["row_number"],
                    field_name=diff["field_name"],
                    old_value=str(diff["old_value"]) if diff["old_value"] is not None else None,
                    new_value=str(diff["new_value"]) if diff["new_value"] is not None else None,
                    impact_eta=diff["impact_eta"],
                    impact_cost=diff["impact_cost"],
                    impact_risk=diff["impact_risk"],
                    is_j_plus_1=diff["is_j_plus_1"],
                    ignored_reason=diff["ignored_reason"],
                )
                self.db.add(planning_diff)
            self.db.commit()

        return {
            "planning_id": planning.id,
            "week": planning.week.isoformat() if planning.week else None,
            "status": planning.status,
            "diff_count": len(diffs),
            "j_plus_1_day": j_plus_1_day,
            "diffs": diffs,
            "ignored": [item for item in diffs if item["ignored_reason"]],
        }

    def get_detected_changes(self, planning_id: int) -> Dict[str, Any]:
        diffs = self.db.query(PlanningDiff).filter(PlanningDiff.planning_id == planning_id).order_by(PlanningDiff.detected_at.desc()).all()
        return {
            "planning_id": planning_id,
            "changes": [
                {
                    "id": diff.id,
                    "delivery_id": diff.delivery_id,
                    "delivery_day": diff.delivery_day,
                    "row_number": diff.row_number,
                    "field_name": diff.field_name,
                    "old_value": diff.old_value,
                    "new_value": diff.new_value,
                    "impact_eta": diff.impact_eta,
                    "impact_cost": diff.impact_cost,
                    "impact_risk": diff.impact_risk,
                    "is_j_plus_1": diff.is_j_plus_1,
                    "ignored_reason": diff.ignored_reason,
                    "detected_at": diff.detected_at.isoformat() if diff.detected_at else None,
                }
                for diff in diffs
            ]
        }

    def get_diff_history(self, planning_id: int) -> List[Dict[str, Any]]:
        return self.get_detected_changes(planning_id)["changes"]

    def revalidate_planning(self, planning_id: int, user_id: int) -> PlanningVersion:
        planning = self.db.query(PlanningVersion).filter(PlanningVersion.id == planning_id).first()
        if not planning:
            raise ValueError("Planning version not found")

        if planning.status not in ("PENDING_REVIEW", "MODIFIED_AFTER_VALIDATION"):
            raise ValueError("Planning version must be pending review or modified after validation to revalidate")

        planning.status = "REVALIDATED"
        planning.validated_at = datetime.now(timezone.utc)
        planning.validated_by = user_id
        planning.reviewed_by = user_id
        planning.last_review_at = datetime.now(timezone.utc)
        self.db.add(planning)
        self.db.commit()
        self.db.refresh(planning)

        audit = PlanningChangeLog(
            planning_id=planning.id,
            source=AUDIT_SOURCE_USER,
            modified_by=user_id,
            field_name="planning_status",
            old_value=None,
            new_value="REVALIDATED",
            reason="Planning revalidated by user",
            change_type=AUDIT_TYPE_REVALIDATION,
            user_id=user_id,
        )
        self.db.add(audit)
        self.db.commit()

        return planning

    def reject_planning_changes(self, planning_id: int, user_id: int, reason: Optional[str] = None) -> PlanningVersion:
        planning = self.db.query(PlanningVersion).filter(PlanningVersion.id == planning_id).first()
        if not planning:
            raise ValueError("Planning version not found")

        if planning.status not in ("PENDING_REVIEW", "MODIFIED_AFTER_VALIDATION"):
            raise ValueError("Planning version must be pending review or modified after validation to reject")

        diffs = self.db.query(PlanningDiff).filter(PlanningDiff.planning_id == planning_id, PlanningDiff.is_j_plus_1 == True, PlanningDiff.ignored_reason == None).all()
        for diff in diffs:
            if diff.delivery_id:
                delivery = self.db.query(Livraison).filter(Livraison.id == diff.delivery_id).first()
                if delivery and diff.field_name in VALID_FIELDS:
                    setattr(delivery, diff.field_name, diff.old_value)
                    self.db.add(delivery)

        planning.status = "REJECTED_CHANGES"
        planning.reviewed_by = user_id
        planning.last_review_at = datetime.now(timezone.utc)
        self.db.add(planning)

        audit = PlanningChangeLog(
            planning_id=planning.id,
            source=AUDIT_SOURCE_USER,
            modified_by=user_id,
            field_name="planning_status",
            old_value=None,
            new_value="REJECTED_CHANGES",
            reason=reason or "Changes were rejected during review",
            change_type=AUDIT_TYPE_MANUAL_UPDATE,
            user_id=user_id,
        )
        self.db.add(audit)
        self.db.commit()

        return planning
