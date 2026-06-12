from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from app.models.user import User
from app.models.transport import UserCreate, TokenData
import os

# TODO(TMS P0 security — see docs/TMS_ROADMAP.md §10):
#   1. SECRET_KEY falls back to a hardcoded value — fail fast if JWT_SECRET is
#      unset in production instead of signing tokens with a known key.
#   2. passlib 1.7.4 is BROKEN against bcrypt>=4.1 (it reads the removed
#      bcrypt.__about__) — hash_password/verify_password raise. Pin bcrypt==4.0.1
#      or move to a maintained hasher. scripts/seed_from_files.py hashes the admin
#      user with the bcrypt lib directly to work around this.
SECRET_KEY = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    # TODO(TMS P0 security): this dev fallback hands out a fake ADMIN when no token
    # is present — i.e. every endpoint is open by default. Gate this behind an
    # explicit env flag (e.g. AUTH_DEV_BYPASS=1) and 401 otherwise in production.
    if creds is None:
        return {"username": "dev", "role": "admin"}
    payload = decode_token(creds.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return {"username": payload["sub"], "role": payload.get("role", "admin")}


def require_role(*roles: str):
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return _dep


# Whether to *enforce* auth on protected routes. Off by default so the
# offline-first frontend (which ships without a login flow) keeps working;
# set REQUIRE_AUTH=1 in a real deployment to enforce 403 on anonymous calls.
def _auth_enforced() -> bool:
    return os.getenv("REQUIRE_AUTH", "").strip().lower() in ("1", "true", "yes", "on")


# auto_error=False so we control the no-credentials case ourselves: enforce 403
# only when REQUIRE_AUTH is set, otherwise fall back to the dev user like
# get_current_user does for the rest of the app.
_protected_bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_protected_bearer),
) -> dict:
    """Auth dependency for production-sensitive routes (plan generation,
    dashboards).

    - A present-but-invalid/expired token is ALWAYS rejected with 401.
    - A missing token returns 403 when REQUIRE_AUTH is enabled, otherwise falls
      back to the offline dev user so the tokenless frontend still works.

    This mirrors the codebase's offline-first design (get_current_user has the
    same dev fallback) while letting a real deployment lock these routes down
    with a single environment flag.
    """
    if credentials is None:
        if _auth_enforced():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
        return {"username": "dev", "role": "admin"}
    payload = decode_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return {"username": payload["sub"], "role": payload.get("role", "admin")}


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return verify_password(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return hash_password(password)

    def get_user(self, username: str) -> Optional[User]:
        try:
            return self.db.query(User).filter(User.username == username).first()
        except SQLAlchemyError:
            return None

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        user = self.get_user(username)
        if not user:
            return None
        if not user.is_active:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    def create_user(self, user: UserCreate) -> User:
        hashed = self.get_password_hash(user.password)
        email = user.email or f"{user.username}@coficab.local"
        db_user = User(username=user.username, email=email, password_hash=hashed)
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        return create_token(data, expires_delta=expires_delta)

    def decode_access_token(self, token: str) -> Optional[dict]:
        return decode_token(token)

    def get_current_username(self, token: str) -> Optional[str]:
        payload = self.decode_access_token(token)
        if not payload:
            return None
        return payload.get("sub")
