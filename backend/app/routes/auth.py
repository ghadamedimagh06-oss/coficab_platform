from datetime import timedelta
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth_service import AuthService, get_current_user, require_role
from app.models.user import User
from app.models.transport import UserCreate, Token

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


async def _login_payload(request: Request) -> tuple[str, str]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid JSON body") from exc
    else:
        raw = (await request.body()).decode("utf-8")
        payload = {key: _first(value) for key, value in parse_qs(raw).items()}

    username = _first(payload.get("username")) or _first(payload.get("email"))
    password = _first(payload.get("password"))
    if not username or password is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="username/email and password are required")
    return str(username), str(password)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    db: Session = Depends(get_db)
):
    """User authentication"""
    username, password = await _login_payload(request)
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = auth_service.create_access_token(
        data={"sub": user.username, "role": getattr(user, "role", "admin")}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": getattr(user, "role", "admin")}

@router.post("/register", response_model=Token)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """User registration"""
    auth_service = AuthService(db)
    # Check if user already exists
    existing_user = auth_service.get_user(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    user = auth_service.create_user(user_data)
    access_token_expires = timedelta(minutes=30)
    access_token = auth_service.create_access_token(
        data={"sub": user.username, "role": getattr(user, "role", "admin")}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": getattr(user, "role", "admin")}
