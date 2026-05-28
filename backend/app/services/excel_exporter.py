"""Excel round-trip export for generated daily planning."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from openpyxl import load_workbook


FIELD_ALIASES = {
    "driver": {"driver", "chauffeur"},
    "vehicle": {"vehicle", "camion", "truck"},
    "etd": {"etd", "departure", "heure_depart"},
    "eta": {"eta", "arrival", "heure_arrivee"},
    "status": {"status", "statut"},
    "client": {"client", "customer"},
    "position_count": {"quantity", "position", "position_nbr", "position_number", "position_no", "pallets"},
    "gross_weight_kg": {"gross_weight", "total_gross_weight", "pallet_weight"},
}


def export_plan_to_xlsx(source_path: Path, plan: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    out_name = f"{source_path.stem}_edited_{timestamp}{source_path.suffix}"
    out_path = out_dir / out_name
    shutil.copy2(source_path, out_path)

    workbook = load_workbook(out_path)
    sheet = workbook["Planning"] if "Planning" in workbook.sheetnames else workbook.active
    header_row, columns = _find_header(sheet)

    row_lookup = _delivery_lookup(plan)
    for delivery in row_lookup.values():
        if delivery.get("status") == "new":
            _append_delivery(sheet, columns, delivery)
            continue

        raw = delivery.get("raw") or {}
        excel_row = int(raw.get("excel_row_index") or 0) or None
        if excel_row is None:
            row_number = int(delivery.get("id") or 0)
            excel_row = header_row + row_number if row_number > 0 else None
        if excel_row and excel_row <= sheet.max_row:
            _write_delivery(sheet, columns, excel_row, delivery)

    workbook.save(out_path)
    return out_path


def _delivery_lookup(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for truck in plan.get("trucks", []):
        label = truck.get("truck_label") or f"Truck {truck.get('truck_id')}"
        for trip in truck.get("trips", []):
            for stop in trip.get("stops", []):
                result[str(stop.get("id") or id(stop))] = {
                    **stop,
                    "_vehicle": label,
                    "_driver": stop.get("constraints", {}).get("required_driver") or "",
                }
    for stop in plan.get("unassigned", []):
        result[str(stop.get("id") or id(stop))] = stop
    return result


def _find_header(sheet) -> tuple[int, dict[str, int]]:
    best_row = 1
    best_columns: dict[str, int] = {}
    for row_idx in range(1, min(sheet.max_row, 8) + 1):
        columns: dict[str, int] = {}
        for cell in sheet[row_idx]:
            normalized = _normalize(cell.value)
            for field, aliases in FIELD_ALIASES.items():
                if normalized in aliases and field not in columns:
                    columns[field] = cell.column
        if len(columns) > len(best_columns):
            best_row = row_idx
            best_columns = columns
    return best_row, best_columns


def _write_delivery(sheet, columns: dict[str, int], row_idx: int, delivery: dict[str, Any]) -> None:
    values = {
        "driver": delivery.get("_driver") or delivery.get("constraints", {}).get("required_driver") or "",
        "vehicle": delivery.get("_vehicle") or "",
        "etd": delivery.get("etd"),
        "eta": delivery.get("eta"),
        "status": delivery.get("status"),
        "client": delivery.get("client"),
        "position_count": delivery.get("quantity_positions") or delivery.get("position_count"),
        "gross_weight_kg": delivery.get("quantity_kg"),
    }
    for field, value in values.items():
        col = columns.get(field)
        if col and value is not None:
            sheet.cell(row=row_idx, column=col).value = value


def _append_delivery(sheet, columns: dict[str, int], delivery: dict[str, Any]) -> None:
    row_idx = sheet.max_row + 1
    _write_delivery(sheet, columns, row_idx, delivery)


def _normalize(value: Optional[Any]) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower().replace("\xa0", " ")
    text = text.replace("-", " ").replace(".", " ")
    return "_".join(text.split())
