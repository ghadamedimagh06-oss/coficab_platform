"""
Ingestion service: turns weekly Excel files into demandes_local rows.

Pipeline per file:
  parse → validate each row → upsert client lookup → insert DemandeLocal
  → move file to archive/<YYYY-MM-DD>/ → write IngestionLog
"""

import logging
import shutil
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.models.demande import DemandeLocal, StatutDemande, Priorite
from app.models.client import Client
from app.models.ingestion_log import IngestionLog

log = logging.getLogger(__name__)

_REQUIRED = {"quantite_kg", "date_livraison"}
_PRIO_VALUES = {p.value for p in Priorite}


class IngestionResult:
    def __init__(self):
        self.inserted = 0
        self.skipped = 0
        self.errors: list[str] = []
        self.warnings: list[str] = []


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_excel(self, file_path: Path, archive_base: Path | None = None) -> IngestionResult:
        result = IngestionResult()
        try:
            df = pd.read_excel(file_path)
            df.columns = [str(c).strip().lower() for c in df.columns]
        except Exception as exc:
            result.errors.append(f"Cannot open {file_path.name}: {exc}")
            self._write_log(file_path, "failed", result)
            return result

        for idx, row in df.iterrows():
            try:
                warn = self._ingest_row(row.to_dict())
                result.inserted += 1
                result.warnings.extend(f"row {idx+2}: {w}" for w in warn)
            except ValueError as ve:
                result.skipped += 1
                result.errors.append(f"row {idx+2}: {ve}")

        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            result.errors.append(f"DB commit failed: {exc}")
            result.inserted = 0

        if archive_base:
            self._archive(file_path, archive_base)

        status = "success" if result.inserted and not result.skipped else (
            "partial" if result.inserted else "failed"
        )
        self._write_log(file_path, status, result)
        return result

    def ingest_demande(self, payload: dict) -> DemandeLocal:
        """Insert a single demande from a validated dict (manual entry / API)."""
        warnings = self._ingest_row(payload)
        self.db.commit()
        if warnings:
            log.warning("ingest_demande warnings: %s", warnings)
        # Return the last-added demande (just committed)
        return self.db.query(DemandeLocal).order_by(DemandeLocal.id.desc()).first()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ingest_row(self, row: dict) -> list[str]:
        """Validate and add a DemandeLocal to the session. Returns soft warnings."""
        warnings: list[str] = []

        # --- Required fields ---
        for f in _REQUIRED:
            if f not in row or _isna(row[f]):
                raise ValueError(f"missing required field: {f}")

        # --- Client resolution ---
        client = self._resolve_client(row)
        if client is None:
            name = row.get("client_name") or row.get("client_id") or "(unknown)"
            raise ValueError(f"client not found: {name}. Add the client first.")

        # --- quantite_kg ---
        try:
            qty = float(row["quantite_kg"])
        except (TypeError, ValueError):
            raise ValueError(f"quantite_kg is not numeric: {row['quantite_kg']!r}")
        if qty <= 0 or qty > 50_000:
            raise ValueError(f"quantite_kg out of range: {qty}")

        # --- date_livraison ---
        try:
            dliv = pd.to_datetime(row["date_livraison"]).date()
        except Exception:
            raise ValueError(f"invalid date_livraison: {row['date_livraison']!r}")
        yesterday = date.today().replace(day=date.today().day - 1) if date.today().day > 1 else date.today()
        if dliv < date.today():
            raise ValueError(f"date_livraison in the past: {dliv}")

        # --- nombre_palettes (optional, soft validation) ---
        nb_pal = None
        raw_pal = row.get("nombre_palettes")
        if raw_pal is not None and not _isna(raw_pal):
            try:
                nb_pal = int(raw_pal)
                if nb_pal < 0 or nb_pal > 100:
                    raise ValueError
            except (TypeError, ValueError):
                warnings.append(f"nombre_palettes ignored (invalid value: {raw_pal!r})")
                nb_pal = None

        # --- Client time-window check (soft) ---
        if client.fenetre_ouverture is None:
            warnings.append(f"client {client.nom} has no time window — planner review needed")

        # --- Oversize check (soft) ---
        max_cap = self._max_truck_capacity()
        if max_cap and qty > max_cap:
            warnings.append(
                f"quantite_kg {qty} exceeds largest truck capacity {max_cap} — delivery will need splitting"
            )

        # --- priorite ---
        prio_raw = str(row.get("priorite") or "NORMALE").strip().upper()
        prio = prio_raw if prio_raw in _PRIO_VALUES else "NORMALE"

        # --- heure_arrivee_souhaitee ---
        heure = None
        raw_h = row.get("heure_arrivee_souhaitee")
        if raw_h is not None and not _isna(raw_h):
            try:
                heure = pd.to_datetime(str(raw_h)).time()
            except Exception:
                warnings.append(f"heure_arrivee_souhaitee ignored (parse failed: {raw_h!r})")

        demande = DemandeLocal(
            client_id=client.id,
            quantite_kg=qty,
            nombre_palettes=nb_pal,
            date_livraison=dliv,
            heure_arrivee_prevue=datetime.combine(dliv, heure) if heure else None,
            priorite=Priorite(prio),
            statut=StatutDemande.NOUVELLE,
            commentaire=row.get("commentaire") or None,
            source_import=str(row.get("source_import") or "excel"),
        )
        self.db.add(demande)
        return warnings

    def _resolve_client(self, row: dict) -> Client | None:
        cid = row.get("client_id")
        if cid is not None and not _isna(cid):
            try:
                c = self.db.query(Client).filter(Client.id == int(cid)).first()
                if c:
                    return c
            except (TypeError, ValueError):
                pass
        name = row.get("client_name")
        if name and not _isna(name):
            return (
                self.db.query(Client)
                .filter(Client.nom.ilike(str(name).strip()))
                .first()
            )
        return None

    def _max_truck_capacity(self) -> float | None:
        from app.models.camion import Camion
        try:
            from sqlalchemy import func
            row = self.db.query(func.max(Camion.capacite_kg)).scalar()
            return float(row) if row else None
        except Exception:
            return None

    def _archive(self, file_path: Path, archive_base: Path) -> None:
        dest_dir = archive_base / date.today().isoformat()
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(file_path), str(dest_dir / file_path.name))
        except Exception as exc:
            log.warning("Archive move failed for %s: %s", file_path.name, exc)

    def _write_log(self, path: Path, status: str, r: IngestionResult) -> None:
        entry = IngestionLog(
            file_name=path.name,
            file_path=str(path),
            status=status,
            inserted_rows=r.inserted,
            total_rows=r.inserted + r.skipped,
            error_message="\n".join((r.errors + r.warnings)[:50]) or None,
        )
        self.db.add(entry)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()

    # ------------------------------------------------------------------
    # Legacy compatibility (called by old routes / tests)
    # ------------------------------------------------------------------

    def ingest_excel_file(self, file_path: str, file_name: str | None = None) -> dict:
        """Shim so old routes still work. Delegates to ingest_excel."""
        result = self.ingest_excel(Path(file_path))
        fn = file_name or Path(file_path).name
        status = "success" if result.inserted and not result.skipped else (
            "partial" if result.inserted else "failed"
        )
        return {
            "file_name": fn,
            "status": status,
            "total_rows": result.inserted + result.skipped,
            "inserted_rows": result.inserted,
            "error_count": result.skipped,
            "errors": result.errors,
        }

    def get_ingestion_history(self, limit: int = 50) -> list:
        logs = (
            self.db.query(IngestionLog)
            .order_by(IngestionLog.import_date.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": lg.id,
                "file_name": lg.file_name,
                "import_date": lg.import_date.isoformat() if lg.import_date else None,
                "status": lg.status,
                "inserted_rows": lg.inserted_rows,
                "total_rows": lg.total_rows,
                "error_message": lg.error_message,
            }
            for lg in logs
        ]


def _isna(val) -> bool:
    try:
        return pd.isna(val)
    except Exception:
        return val is None
