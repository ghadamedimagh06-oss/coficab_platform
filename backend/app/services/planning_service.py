"""Planning Service for CofICab Platform

Handles weekly Excel planning ingestion, validated-planning comparison,
J+1 change detection, review operations, and audit history tracking.
"""

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

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
        candidate_columns = [c for c in df.columns if str(c).strip().lower() in ("day", "weekday", "delivery_day", "jour")]
        if candidate_columns:
            day_col = candidate_columns[0]
            return [self._normalize_weekday(value) for value in df[day_col].tolist()]

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

    def parse_weekly_planning(self, file_path: str) -> Dict[str, Any]:
        df = pd.read_excel(file_path)
        if df.empty:
            raise ValueError("Excel file contains no planning rows")

        weekday_values = self._infer_delivery_day(df)
        rows = []
        for index, row in df.iterrows():
            row_data = {
                "row_number": int(index + 1),
                "delivery_day": weekday_values[index] if index < len(weekday_values) else None,
                "driver": str(row.get("driver", "")).strip() if not pd.isna(row.get("driver", "")) else "",
                "vehicle": str(row.get("vehicle", "")).strip() if not pd.isna(row.get("vehicle", "")) else "",
                "start_location": str(row.get("start", row.get("start_location", ""))).strip() if not pd.isna(row.get("start", row.get("start_location", ""))) else "",
                "end_location": str(row.get("end", row.get("end_location", ""))).strip() if not pd.isna(row.get("end", row.get("end_location", ""))) else "",
                "distance_km": float(row.get("distance", row.get("distance_km", 0))) if not pd.isna(row.get("distance", row.get("distance_km", 0))) else 0.0,
                "status": str(row.get("status", "pending")).strip() if not pd.isna(row.get("status", "pending")) else "pending",
                "priority": str(row.get("priority", "normal")).strip() if not pd.isna(row.get("priority", "normal")) else "normal",
                "notes": str(row.get("notes", "")).strip() if not pd.isna(row.get("notes", "")) else None,
                "client": str(row.get("client", row.get("customer", ""))).strip() if not pd.isna(row.get("client", row.get("customer", ""))) else None,
                "etd": str(row.get("etd", "")).strip() if not pd.isna(row.get("etd", "")) else None,
                "eta": str(row.get("eta", "")).strip() if not pd.isna(row.get("eta", "")) else None,
                "quantity": int(row.get("quantity", 0)) if not pd.isna(row.get("quantity", 0)) and str(row.get("quantity", 0)).strip() != "" else None,
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
            if not row["driver"] or not row["vehicle"] or not row["start_location"] or not row["end_location"]:
                continue
            if row["distance_km"] <= 0:
                continue

            livraison = Livraison(
                planning_id=planning.id,
                delivery_day=row["delivery_day"],
                delivery_date=row["delivery_date"],
                row_number=row["row_number"],
                client=row["client"],
                etd=row["etd"],
                eta=row["eta"],
                quantity=row["quantity"],
                driver=row["driver"],
                vehicle=row["vehicle"],
                start_location=row["start_location"],
                end_location=row["end_location"],
                distance_km=row["distance_km"],
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
                    timestamp=datetime.utcnow(),
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
            planning.last_review_at = datetime.utcnow()
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
        planning.validated_at = datetime.utcnow()
        planning.validated_by = user_id
        planning.reviewed_by = user_id
        planning.last_review_at = datetime.utcnow()
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
        planning.last_review_at = datetime.utcnow()
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
