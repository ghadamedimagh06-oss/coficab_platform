from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# TODO(TMS P0 — see docs/TMS_ROADMAP.md §1 & §10):
#   - Don't ship a hardcoded postgres:postgres default; require DATABASE_URL via a
#     real .env / secret manager and fail fast if missing in production.
#   - Replace Base.metadata.create_all (in app/main.py) with Alembic migrations so
#     schema is versioned/reproducible — and fix the clients.id "manual PK, no
#     sequence" quirk deliberately in a migration.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/coficab_db")

# Create engine with connection pooling and error handling
try:
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,           # Maintain 5 connections in pool
        max_overflow=10,       # Allow up to 10 additional connections
        pool_pre_ping=True,    # Test connections before using them
        pool_recycle=300,      # Recycle connections after 5 minutes
        pool_timeout=30,       # Timeout for getting connection from pool
        echo=False             # Set to True for SQL debugging
    )
    # Test the connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("Database connection successful")
except Exception as e:
    print(f"Database connection failed: {e}")
    print("Running in offline mode - database operations will fail")
    engine = None

class OfflineSession:
    def close(self):
        return None


class OfflineSessionFactory:
    def __call__(self):
        return OfflineSession()

    def __bool__(self):
        return False


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else OfflineSessionFactory()

Base = declarative_base()

def get_db():
    if not SessionLocal:
        raise Exception("Database not available - check DATABASE_URL and PostgreSQL connection")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_optional():
    """Optional database dependency - returns None if DB unavailable instead of raising"""
    if not SessionLocal:
        yield None
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
