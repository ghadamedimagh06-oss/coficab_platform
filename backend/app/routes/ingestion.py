from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
import datetime
import os
from pathlib import Path
from app.database import get_db, get_db_optional
from app.services.ingestion_service import IngestionService
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
