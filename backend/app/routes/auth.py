from datetime import timedelta
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth_service import AuthService, get_current_user, require_role
from app.models.user import User
from app.models.transport import UserCreate, Token

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
VALID_ROLES = {"viewer", "planner", "admin"}


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    email: str | None = None
    password: str = Field(..., min_length=1)
    role: str = "viewer"
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    email: str | None = None
    password: str | None = Field(default=None, min_length=1)
    role: str | None = None
    is_active: bool | None = None


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "date_creation": user.date_creation.isoformat() if user.date_creation else None,
    }


def _validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {sorted(VALID_ROLES)}")
    return normalized


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
        data={"sub": user.username, "role": getattr(user, "role", "viewer")}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": getattr(user, "role", "viewer")}

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
        data={"sub": user.username, "role": getattr(user, "role", "viewer")}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": getattr(user, "role", "viewer")}


@router.get("/me")
async def me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    username = current_user.get("username")
    user = db.query(User).filter(User.username == username).first() if username else None
    if user is None:
        if username == "dev":
            return {
                "id": None,
                "username": "dev",
                "email": "dev@coficab.local",
                "role": "admin",
                "is_active": True,
                "date_creation": None,
            }
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return _user_dict(user)


@router.get("/users")
async def list_users(
    _user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.username).all()
    return {"users": [_user_dict(user) for user in users], "count": len(users)}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate,
    _user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    role = _validate_role(payload.role)
    email = payload.email or f"{payload.username}@coficab.local"
    auth_service = AuthService(db)

    if auth_service.get_user(payload.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=payload.username,
        email=email,
        password_hash=auth_service.get_password_hash(payload.password),
        role=role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_dict(user)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    _user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    if payload.email is not None and payload.email != user.email:
        if db.query(User).filter(User.email == payload.email, User.id != user.id).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = payload.email
    if payload.role is not None:
        user.role = _validate_role(payload.role)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = AuthService(db).get_password_hash(payload.password)

    db.commit()
    db.refresh(user)
    return _user_dict(user)
