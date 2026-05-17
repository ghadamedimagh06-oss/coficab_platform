"""
Database Configuration for CofICab Platform
PostgreSQL connection with SQLAlchemy
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/coficab_db")

# Create SQLAlchemy engine with connection pooling
try:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,           # Maintain 10 connections in pool
        max_overflow=20,        # Allow up to 20 additional connections
        pool_pre_ping=True,     # Test connections before using them
        pool_recycle=300,       # Recycle connections after 5 minutes
        pool_timeout=30,        # Timeout for getting connection from pool
        echo=False              # Set to True for SQL debugging
    )

    # Test the connection
    with engine.connect() as conn:
        conn.execute("SELECT 1")
    print("✅ Database connection successful")

except Exception as e:
    print(f"❌ Database connection failed: {e}")
    print("Please ensure PostgreSQL is running and DATABASE_URL is correct")
    raise

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

def get_db():
    """Database dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_optional():
    """Optional database dependency - returns None if unavailable instead of raising"""
    try:
        db = SessionLocal()
        yield db
    except Exception:
        yield None