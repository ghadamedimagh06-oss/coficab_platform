from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from app.models.user import User
from app.models.transport import UserCreate, TokenData
from app.config import auth_enforced, dev_bypass_allowed, jwt_secret

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
bearer_scheme = HTTPBearer(auto_error=False)

# bcrypt operates on at most 72 bytes; longer inputs are silently truncated by
# most libs, so we truncate explicitly for deterministic behaviour. We call the
# bcrypt package directly (not passlib, which is unmaintained and reads the
# removed bcrypt.__about__ on bcrypt>=4.1, emitting errors).
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = (password or "").encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    pw = (plain_password or "").encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pw, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    # The dev fallback hands out a 'dev' admin when no token is present so the
    # tokenless offline frontend works. It is DISABLED in production (and when
    # REQUIRE_AUTH is set), where a missing token is rejected. See app.config.
    if creds is None:
        if dev_bypass_allowed():
            return {"username": "dev", "role": "admin"}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    # Least privilege: a token without an explicit role claim is treated as a
    # read-only viewer, never an admin.
    return {"username": payload["sub"], "role": payload.get("role", "viewer")}


def require_role(*roles: str):
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return _dep


# auto_error=False so we control the no-credentials case ourselves.
_protected_bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_protected_bearer),
) -> dict:
    """Auth dependency for production-sensitive routes (plan generation,
    dashboards, execution/ePOD).

    - A present-but-invalid/expired token is ALWAYS rejected with 401.
    - A missing token returns 403 when auth is enforced (production or
      REQUIRE_AUTH), otherwise falls back to the offline dev user so the
      tokenless frontend still works. See app.config.auth_enforced.
    """
    if credentials is None:
        if auth_enforced():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
        return {"username": "dev", "role": "admin"}
    payload = decode_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    # Least privilege: a token without an explicit role claim is treated as a
    # read-only viewer, never an admin.
    return {"username": payload["sub"], "role": payload.get("role", "viewer")}


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
