from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
import datetime
import os
import shutil
from pathlib import Path
from app.database import get_db, get_db_optional
from app.services.ingestion_service import IngestionService
from app.models.ingestion_log import IngestionLog
from app.models.user import User
from app.services.auth_service import AuthService, oauth2_scheme, require_role
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from fastapi import HTTPException, status
    from app.models.transport import TokenData

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    auth_service = AuthService(db)
    user = auth_service.get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[3]
WEEKLY_DIR = PROJECT_ROOT / "weekly planning"
UPLOAD_DIR = WEEKLY_DIR / "uploads"
ARCHIVE_DIR = PROJECT_ROOT / "archive"

class IngestionTrigger(BaseModel):
    file_path: str
    timestamp: int


class IngestionDataRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    rows: List[Dict[str, Any]]


def validate_file_path(file_path: str) -> str:
    """Validate and secure file path"""
    # Resolve the path to prevent directory traversal
    resolved_path = Path(file_path).resolve()

    # Ensure it's within the shared_folder directory
    shared_folder = Path("shared_folder").resolve()
    if not str(resolved_path).startswith(str(shared_folder)):
        raise HTTPException(status_code=400, detail="File must be in shared_folder directory")

    # Check file extension
    if resolved_path.suffix.lower() != '.xlsx':
        raise HTTPException(status_code=400, detail="Only .xlsx files are allowed")

    # Check file size (5MB limit)
    if resolved_path.exists():
        file_size = resolved_path.stat().st_size
        if file_size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=400, detail="File size must be less than 5MB")

    return str(resolved_path)


def _log_dict(log: IngestionLog) -> dict:
    return {
        "id": log.id,
        "file_name": log.file_name,
        "file_path": log.file_path,
        "import_date": log.import_date.isoformat() if log.import_date else None,
        "status": log.status,
        "inserted_rows": log.inserted_rows,
        "total_rows": log.total_rows,
        "error_message": log.error_message,
        "processed_at": log.processed_at.isoformat() if log.processed_at else None,
        "archived_path": log.archived_path,
    }


@router.post("/data")
async def ingest_data_payload(
    request: IngestionDataRequest,
    current_user: dict = Depends(require_role("planner", "admin")),
    db: Optional[Session] = Depends(get_db_optional),
):
    """Validate direct JSON ingestion payloads.

    Workbook ingestion remains the authoritative path for persistence. This
    endpoint exists so clients get explicit validation errors instead of a 404
    when they submit row payloads directly.
    """
    unsafe_chars = set('<>:"/\\|?*')
    if any(char in unsafe_chars for char in request.filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not request.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx filenames are accepted")

    return {
        "status": "empty" if not request.rows else "validated",
        "file_name": request.filename,
        "total_rows": len(request.rows),
        "inserted_rows": 0,
        "persisted": False,
        "message": "Use /api/ingestion/trigger with a workbook path to persist ingestion results.",
    }


@router.post("/demande")
async def create_manual_demande(
    request: Dict[str, Any],
    current_user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    service = IngestionService(db)
    try:
        demande = service.ingest_demande({**request, "source_import": "manual"})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "id": demande.id,
        "client_id": demande.client_id,
        "quantite_kg": float(demande.quantite_kg),
        "date_livraison": demande.date_livraison.isoformat(),
        "statut": demande.statut.value if hasattr(demande.statut, "value") else demande.statut,
        "source_import": demande.source_import,
    }


# Upload hardening (W4.6): cap size and verify the file is really an .xlsx
# (an Office Open XML workbook is a ZIP container, so it starts with "PK\x03\x04").
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
_XLSX_MAGIC = b"PK\x03\x04"


@router.post("/upload")
async def upload_planning_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are accepted")
    # Reject the wrong content type early when the client declares one.
    if file.content_type and file.content_type not in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
        "application/zip",
    ):
        raise HTTPException(status_code=400, detail=f"Unexpected content type: {file.content_type}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name
    target = UPLOAD_DIR / safe_name

    # Stream to disk in chunks, enforcing the size cap as we go (so an oversized
    # upload can't fill the disk) and validating the ZIP/xlsx magic on the first
    # bytes (so a renamed .exe/.csv is rejected, not parsed).
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    first = True
    try:
        with target.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                if first:
                    if not chunk.startswith(_XLSX_MAGIC):
                        raise HTTPException(status_code=400, detail="File is not a valid .xlsx workbook")
                    first = False
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_MB} MB limit")
                out.write(chunk)
        if written == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
    except HTTPException:
        target.unlink(missing_ok=True)  # don't leave a partial/invalid file behind
        raise

    result = IngestionService(db).ingest_excel(target, ARCHIVE_DIR)
    status = "success" if result.inserted and not result.skipped else (
        "partial" if result.inserted else "failed"
    )
    return {
        "status": status,
        "file_name": safe_name,
        "inserted_rows": result.inserted,
        "skipped_rows": result.skipped,
        "errors": result.errors,
    }


@router.get("/logs")
async def get_ingestion_logs(
    limit: int = 20,
    current_user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 200))
    logs = db.query(IngestionLog).order_by(IngestionLog.import_date.desc()).limit(limit).all()
    return {"logs": [_log_dict(log) for log in logs], "count": len(logs)}


@router.get("/logs/{log_id}")
async def get_ingestion_log(
    log_id: int,
    current_user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    log = db.get(IngestionLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="ingestion log not found")
    return _log_dict(log)


@router.post("/logs/{log_id}/retry")
async def retry_ingestion_log(
    log_id: int,
    current_user: dict = Depends(require_role("planner", "admin")),
    db: Session = Depends(get_db),
):
    log = db.get(IngestionLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="ingestion log not found")
    if log.status not in {"failed", "partial"}:
        raise HTTPException(status_code=400, detail="Only failed or partial imports can be retried")

    path = Path(log.file_path)
    if not path.exists() or path.suffix.lower() != ".xlsx":
        raise HTTPException(status_code=400, detail="original workbook is unavailable")

    result = IngestionService(db).ingest_excel(path)
    status = "success" if result.inserted and not result.skipped else (
        "partial" if result.inserted else "failed"
    )
    return {
        "status": status,
        "file_name": path.name,
        "inserted_rows": result.inserted,
        "skipped_rows": result.skipped,
        "errors": result.errors,
    }

@router.post("/trigger")
async def trigger_ingestion(
    request: IngestionTrigger,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger data ingestion pipeline"""
    try:
        # Validate and secure file path
        secure_file_path = validate_file_path(request.file_path)

        # Check if file exists
        if not os.path.exists(secure_file_path):
            raise HTTPException(status_code=400, detail=f"File not found: {secure_file_path}")

        # Create ingestion service
        service = IngestionService(db)

        # Add ingestion task to background
        background_tasks.add_task(service.ingest_excel_file, secure_file_path)

        return {
            "status": "ingestion_started",
            "file_path": secure_file_path,
            "message": "Ingestion started in background",
            "timestamp": datetime.datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion: {str(e)}")
