# 11 — Auth & Permissions

> Goal: keep auth boringly simple. Three roles, JWT, password hashing. No OAuth provider, no SSO for v1 — this is an internal tool with ≤ 50 named users.

## Current implementation status

Done:
- `backend/app/services/auth_service.py` hashes passwords, issues/decodes JWTs, provides the dev role helper, and rejects inactive users during login.
- `backend/app/routes/auth.py` exposes `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/auth/me`, `GET /api/auth/users`, `POST /api/auth/users`, and `PATCH /api/auth/users/{id}`.
- Admin user management supports create, list, role change, password reset, and deactivate/reactivate.
- `backend/tests/test_auth_endpoints.py` covers `/me`, admin user management, viewer denial, and inactive-user behavior; `backend/tests/test_auth.py` still covers legacy login/security checks.

Pending:
- Full DB-backed route guards are still pending. Most routers use the shared `require_role` call site, but the helper still trusts token role claims in dev/offline mode instead of re-checking every request against `users`.
- Frontend auth guard wiring remains pending.

## KPI anchor
Indirect, but critical: **plan validation is the moment a KPI delta is committed**. Only `planner` and `admin` may validate. `viewer` reads but never writes. Without role enforcement, the audit trail (skill 05) is meaningless.

---

## Build-order note — stub first, finish later

The README build order says "skill 11 can be done anytime." That is true for **user management** (CRUD, role enforcement). It is **false** for the route dependency.

The `require_role` FastAPI dependency must be imported and applied to every router's write endpoints **before skill 03 routes are written** — otherwise endpoints ship without guards and retrofitting always misses at least one.

Two-line stub that unblocks all other skills during local development:

```python
# backend/app/services/auth_service.py  (dev stub — replace with full impl below)
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer(auto_error=False)

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    # TODO: decode JWT when skill 11 is fully wired
    # Returns a mock admin so every other skill can develop without blocking
    return {"username": "dev", "role": "admin"}

def require_role(*roles: str):
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            from fastapi import HTTPException, status
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user
    return _dep
```

Apply it immediately on every route that mutates state:

```python
# any router file
from app.services.auth_service import require_role

@router.post("/demandes")
def create_demande(..., _=Depends(require_role("planner", "admin"))):
    ...
```

When skill 11 is fully implemented, replace the stub body in `auth_service.py` with real JWT decode. All call sites remain unchanged.

---

## Roles

| Role     | Can read | Can write | Can validate plans | Can manage users |
|----------|----------|-----------|--------------------|------------------|
| `viewer` | ✅ all   | ❌        | ❌                 | ❌               |
| `planner`| ✅ all   | ✅ (plans, demandes, incidents) | ✅ | ❌ |
| `admin`  | ✅ all   | ✅ all    | ✅                 | ✅ (CRUD users, tune optimizer weights) |

Stored in `users.role` (skill 02 schema).

---

## Service: `backend/app/services/auth_service.py`

Already exists. Confirm it does:
1. Password hashing with `passlib[bcrypt]`.
2. JWT issue/verify with `python-jose`, HS256, secret in `JWT_SECRET` env var.
3. Token expiry: 12 hours (planners log in once per shift).

If any of those is missing, add it. Keep the function names stable (`hash_password`, `verify_password`, `create_token`, `decode_token`).

---

## Endpoints

```
POST /api/auth/login        { username, password } → { access_token, role }
POST /api/auth/logout       (client just drops the token; server is stateless)
GET  /api/auth/me           → current user info
POST /api/auth/users        (admin) create user
PATCH /api/auth/users/{id}  (admin) update role, deactivate
```

---

## Dependency: route guards

`backend/app/routes/_deps.py`:

```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth_service import AuthService
from app.models.user import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    auth = AuthService(db)
    username = auth.get_current_username(token)
    if not username: raise HTTPException(401, "Unauthorized")
    u = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not u: raise HTTPException(401, "Inactive or unknown user")
    return u

def require_role(*allowed: str):
    def _check(u: User = Depends(current_user)) -> User:
        if u.role not in allowed:
            raise HTTPException(403, f"role {u.role} not in {allowed}")
        return u
    return _check
```

Use as:

```python
@router.post("/planning/{plan_version_id}/validate")
def validate(plan_version_id: int,
             user: User = Depends(require_role("planner", "admin")),
             db: Session = Depends(get_db)):
    ...
```

---

## Frontend

`frontend/lib/auth.ts`:

```typescript
import { post } from "@/lib/api";

export async function login(username: string, password: string) {
  const res = await post<{ access_token: string; role: string }>(
    "/api/auth/login", { username, password }
  );
  localStorage.setItem("coficab_token", res.access_token);
  localStorage.setItem("coficab_role", res.role);
  return res;
}

export function logout() {
  localStorage.removeItem("coficab_token");
  localStorage.removeItem("coficab_role");
}

export function role(): "viewer" | "planner" | "admin" | null {
  if (typeof window === "undefined") return null;
  return (localStorage.getItem("coficab_role") as any) ?? null;
}
```

Wrap protected pages with a small guard component (`<RequireRole roles={["planner","admin"]}>`). On unauthorized, redirect to `/` (or a 403 card — keep the existing layout, no new design).

---

## Seed admin user

`backend/seed.py`:

```python
from app.database import SessionLocal
from app.services.auth_service import AuthService
from app.models.user import User

def seed():
    db = SessionLocal()
    auth = AuthService(db)
    if not db.query(User).filter(User.username == "admin").first():
        db.add(User(username="admin", email="admin@coficab.local",
                    password_hash=auth.hash_password("changeme"),
                    role="admin"))
        db.commit()
        print("admin user created (password: changeme — change on first login)")
```

---

## Anti-patterns

- ❌ Storing role on the JWT only. Always re-check against the DB (deactivation must take effect immediately).
- ❌ Custom JWT crypto. Use `python-jose`. Hash passwords with bcrypt. No clear-text passwords anywhere.
- ❌ Long-lived tokens (> 24h). Re-issue on activity if needed.
- ❌ Letting `viewer` see auth-sensitive data (other users' details). Keep `/api/auth/users` admin-only.

---

## Verification

1. POST `/api/auth/login` with `admin / changeme` → returns token + `role: "admin"`.
2. GET `/api/auth/me` with that token → returns the admin user.
3. Create a `viewer` user. Try to POST `/api/planning/.../validate` → 403.
4. Promote them to `planner`. Same call → 200.
5. Deactivate them. Same call → 401 immediately.
