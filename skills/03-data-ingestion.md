# 03 — Data Ingestion

> Goal: turn weekly Excel files and emails into rows in `demandes_local`. Everything downstream (planning, KPIs, dispatch) depends on this being correct.

## Current implementation status

Done:
- `backend/app/services/ingestion_service.py` validates Excel rows and manual payloads, writes `demandes_local`, archives uploaded workbooks when requested, and records `ingestion_log` rows.
- `backend/app/services/excel_watcher.py` still watches `weekly planning/` and delegates workbook processing to `IngestionService`.
- `backend/app/routes/ingestion.py` exposes `POST /api/ingestion/demande`, `POST /api/ingestion/upload`, `GET /api/ingestion/logs`, `GET /api/ingestion/logs/{id}`, and `POST /api/ingestion/logs/{id}/retry`.
- `backend/tests/test_ingestion.py` covers the ingestion service and legacy route behavior; `backend/tests/test_ingestion_api.py` covers manual demande creation plus log detail/retry.

Pending:
- Email ingestion is still out of scope for v1; no `ingest_email` implementation is present yet.
- Skill 09 still needs to wire the frontend admin page to the ingestion endpoints.

## KPI anchor
- **OTD / OTIF** (R4-06, R4-02) — wrong delivery dates → false delays.
- **R4-12** — a missing demande means a "lost" client complaint can't be tied back.
- **Load Efficiency** — wrong `quantite_kg` or `nombre_palettes` → broken VRPTW capacity constraint.

Therefore: **validate aggressively, reject silently never, log every reject for the operator**.

---

## Sources

1. **Excel files** dropped into `coficab_platform/weekly planning/`. Already wired by `app/services/excel_watcher.py` (watchdog). Keep it.
2. **Emails** — out of scope for v1. The hook is `IngestionService.ingest_email(message)`. Stub it now, fill later.
3. **Manual entry** — frontend posts to `/api/ingestion/demande` (single demande form).

---

## Pipeline (single file lifecycle)

```
file dropped in weekly planning/
  → watchdog detects (excel_watcher.py)
    → IngestionService.ingest_excel(path)
      → parse rows (pandas)
        → validate(row)            ─ rejects collected
          → upsert client          ← clients.id by name+city
            → insert demandes_local
              → move file to archive/<YYYY-MM-DD>/
                → write ingestion_log row (status, count, errors)
                  → trigger optimizer (skill 04) if file is for today
```

---

## Validation rules (hard fail → row rejected)

| Field            | Rule                                                                         |
|------------------|------------------------------------------------------------------------------|
| `client_id` or `client_name` | At least one resolvable. If only name, fuzzy-match against `clients.nom`. |
| `quantite_kg`    | numeric, `> 0`, `≤ 50_000` (sanity).                                          |
| `date_livraison` | parseable date, `≥ today - 1 day` (no past deliveries).                       |
| `nombre_palettes`| optional, integer, `≥ 0`, `≤ 100`.                                            |
| `priorite`       | optional, must map to enum {`NORMALE`,`HAUTE`,`URGENTE`}; default `NORMALE`.  |
| `heure_arrivee_souhaitee` | optional, time format `HH:MM`.                                       |

Soft warnings (don't reject, but log):
- Client time window unknown → planner gets a flag on the Gantt
- `quantite_kg > camion_max_capacity` → mission will need split

---

## File: `backend/app/services/ingestion_service.py`

```python
import logging
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.demande import DemandeLocal, StatutDemande, Priorite
from app.models.client import Client
from app.models.ingestion_log import IngestionLog

log = logging.getLogger(__name__)

REQUIRED = ["client_id", "quantite_kg", "date_livraison"]

class IngestionResult:
    def __init__(self):
        self.inserted = 0
        self.skipped = 0
        self.errors: list[str] = []

class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def ingest_excel(self, file_path: Path) -> IngestionResult:
        result = IngestionResult()
        try:
            df = pd.read_excel(file_path)
            df.columns = [c.strip().lower() for c in df.columns]
        except Exception as e:
            result.errors.append(f"unable to open {file_path.name}: {e}")
            self._log(file_path, "failed", result)
            return result

        for idx, row in df.iterrows():
            try:
                self._ingest_row(row.to_dict())
                result.inserted += 1
            except ValueError as ve:
                result.skipped += 1
                result.errors.append(f"row {idx+2}: {ve}")
        self.db.commit()
        self._log(file_path, "success" if result.inserted else "partial", result)
        return result

    def _ingest_row(self, row: dict) -> None:
        for f in REQUIRED:
            if f not in row or pd.isna(row[f]):
                raise ValueError(f"missing required field: {f}")

        client = self._resolve_client(row)
        if client is None:
            raise ValueError(f"unknown client: {row.get('client_name') or row.get('client_id')}")

        qty = float(row["quantite_kg"])
        if qty <= 0 or qty > 50_000:
            raise ValueError(f"quantite_kg out of range: {qty}")

        try:
            d = pd.to_datetime(row["date_livraison"]).date()
        except Exception:
            raise ValueError(f"invalid date_livraison: {row['date_livraison']}")
        if d < date.today():
            raise ValueError(f"date_livraison in the past: {d}")

        prio = str(row.get("priorite", "NORMALE")).upper()
        if prio not in {p.value for p in Priorite}:
            prio = "NORMALE"

        heure = None
        if not pd.isna(row.get("heure_arrivee_souhaitee")):
            try:
                heure = pd.to_datetime(str(row["heure_arrivee_souhaitee"])).time()
            except Exception:
                heure = None

        demande = DemandeLocal(
            client_id=client.id,
            quantite_kg=qty,
            nombre_palettes=int(row.get("nombre_palettes") or 0) or None,
            date_livraison=d,
            heure_arrivee_prevue=(
                datetime.combine(d, heure) if heure else None
            ),
            priorite=Priorite(prio),
            statut=StatutDemande.NOUVELLE,
            commentaire=row.get("commentaire") or None,
            source_import="excel",
        )
        self.db.add(demande)

    def _resolve_client(self, row: dict) -> Client | None:
        cid = row.get("client_id")
        if cid is not None and not pd.isna(cid):
            c = self.db.query(Client).filter(Client.id == int(cid)).first()
            if c:
                return c
        name = row.get("client_name")
        if name:
            return self.db.query(Client).filter(Client.nom.ilike(str(name).strip())).first()
        return None

    def _log(self, path: Path, status: str, r: IngestionResult):
        self.db.add(IngestionLog(
            filename=path.name,
            status=status,
            rows_inserted=r.inserted,
            rows_skipped=r.skipped,
            errors="\n".join(r.errors[:50]),
        ))
        self.db.commit()
```

---

## Excel template

`weekly planning/_template.xlsx` — provide one for the operations team. Required columns:

| client_id | client_name | quantite_kg | nombre_palettes | date_livraison | heure_arrivee_souhaitee | priorite | commentaire |
|---|---|---|---|---|---|---|---|

`client_id` and `client_name` are EITHER/OR (one must be present). All others optional except `quantite_kg` and `date_livraison`.

---

## Watchdog wiring (already exists, keep as-is)

`backend/app/services/excel_watcher.py` already calls `IngestionService.ingest_excel(path)`. Confirm the path:
- `WATCH_PATH` env var, defaults to `<repo>/weekly planning/` (this is correct).
- `ARCHIVE_PATH` env var, defaults to `<repo>/archive/` (this is correct).

If the watcher is logging "starting watcher for …" but no files are being picked up, the most common cause is Windows permissions on the share — check that the path resolves and the user running uvicorn has read access.

---

## API endpoints

```
POST   /api/ingestion/upload           multipart/form-data (file)        — admin only
POST   /api/ingestion/demande          { client_id, quantite_kg, … }     — planner
GET    /api/ingestion/logs?limit=20    list of IngestionLog rows
GET    /api/ingestion/logs/{id}        full row + errors
POST   /api/ingestion/logs/{id}/retry  re-runs a failed/partial file
```

Skill 09 wires the existing UI page (`frontend/app/admin/page.jsx`) to these endpoints.

---

## Anti-patterns

- ❌ Inserting demandes from inside a route handler. Route handler → `IngestionService.ingest_demande(payload)`.
- ❌ Skipping the `ingestion_log` write. Operators need to see what failed and retry.
- ❌ Auto-creating clients on the fly (one typo → duplicate row). Require an explicit client resolution; if not found, reject and let the planner add the client first.
- ❌ Mutating the original file. Always move to `archive/`, never edit in place.

---

## Verification

1. Drop `_template.xlsx` (filled with 3 valid + 2 invalid rows) into `weekly planning/`.
2. Watcher should fire within 5s. Check the backend log: `[INGEST] processing file=...`.
3. Query the DB: 3 new `demandes_local` rows, status `NOUVELLE`.
4. Check `ingestion_log`: one row with `status='partial'`, `rows_inserted=3`, `rows_skipped=2`, `errors` contains the 2 row indexes.
5. File should now be in `archive/<YYYY-MM-DD>/_template.xlsx`.
