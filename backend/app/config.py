"""
Centralized runtime configuration & secret handling.

The platform is "offline-first": it must run on a developer laptop with no real
secrets and (optionally) no database. But once APP_ENV=production is set, the
unsafe development defaults become hard errors so we never ship a known JWT key
or a hardcoded postgres:postgres DSN into a real deployment.

See docs/TMS_ROADMAP.md §10.
"""
from __future__ import annotations

import os

# Sentinel placeholder secrets that ship in .env.example / source. These are
# acceptable in dev but must never be used to sign tokens in production.
_PLACEHOLDER_SECRETS = {
    "",
    "your-secret-key-change-in-production",
    "your_secret_key_here_change_in_production",
    "change-me",
    "changeme",
}

# DSNs we refuse to use in production because they carry default credentials.
_INSECURE_DB_DEFAULTS = {
    "postgresql://postgres:postgres@localhost:5432/coficab_db",
    "postgresql://postgres:postgres@localhost/coficab_db",
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_production() -> bool:
    """True when APP_ENV (or ENVIRONMENT) names a production-like environment."""
    env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()
    return env in {"production", "prod", "staging"}


def auth_enforced() -> bool:
    """Whether anonymous (tokenless) access to protected routes is rejected.

    Always enforced in production; otherwise opt-in via REQUIRE_AUTH so the
    tokenless offline frontend keeps working in dev.
    """
    return is_production() or _truthy(os.getenv("REQUIRE_AUTH"))


def dev_bypass_allowed() -> bool:
    """Whether the 'anonymous == dev admin' fallback may be used.

    Never in production. In dev it stays on unless auth is explicitly enforced.
    """
    if is_production():
        return False
    return not _truthy(os.getenv("REQUIRE_AUTH"))


def jwt_secret() -> str:
    """Return the JWT signing secret, refusing placeholder values in production."""
    secret = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or ""
    if is_production() and secret.strip() in _PLACEHOLDER_SECRETS:
        raise RuntimeError(
            "JWT_SECRET is unset or a known placeholder while APP_ENV=production. "
            "Set a strong, unique JWT_SECRET via your secret manager."
        )
    # In dev, fall back to a fixed (clearly-labelled) key so tokens are stable
    # across reloads.
    return secret.strip() or "dev-only-insecure-secret-do-not-use-in-production"


def database_url() -> str | None:
    """Resolve DATABASE_URL.

    Production: DATABASE_URL is required and must not be a default-credential DSN.
    Development: fall back to the local postgres DSN so `seed_from_files.py` and
    the dashboard work out of the box.
    """
    url = (os.getenv("DATABASE_URL") or "").strip()
    if is_production():
        if not url:
            raise RuntimeError(
                "DATABASE_URL is required when APP_ENV=production (no hardcoded default)."
            )
        if url in _INSECURE_DB_DEFAULTS:
            raise RuntimeError(
                "DATABASE_URL uses default postgres:postgres credentials; "
                "provide real credentials in production."
            )
        return url
    return url or "postgresql://postgres:postgres@localhost:5432/coficab_db"
