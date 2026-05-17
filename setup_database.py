#!/usr/bin/env python
"""
Database Setup Script for CofICab Platform
Creates PostgreSQL database and initializes schema
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def setup_database():
    """Setup PostgreSQL database"""
    print("🔧 CofICab Platform - Database Setup\n")
    
    try:
        # Import after path is set
        from sqlalchemy import create_engine, text, inspect
        from dotenv import load_dotenv
        
        # Load environment
        load_dotenv()
        
        # Database connection details
        db_user = os.getenv("POSTGRES_USER", "postgres")
        db_password = os.getenv("POSTGRES_PASSWORD", "postgres")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("POSTGRES_DB", "coficab_db")
        
        print(f"📋 Connection Details:")
        print(f"   Host: {db_host}:{db_port}")
        print(f"   User: {db_user}")
        print(f"   Database: {db_name}\n")
        
        # Connect to default postgres database to create new database
        print("1️⃣  Connecting to PostgreSQL server...")
        default_db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/postgres"
        
        try:
            engine_admin = create_engine(default_db_url, echo=False)
            with engine_admin.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("   ✅ Connected to PostgreSQL\n")
        except Exception as e:
            print(f"   ❌ Failed to connect: {e}")
            print(f"   Make sure PostgreSQL is running on {db_host}:{db_port}\n")
            return False
        
        # Create database if it doesn't exist
        print("2️⃣  Creating database (if not exists)...")
        try:
            with engine_admin.connect() as conn:
                # Set autocommit for CREATE DATABASE
                conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                
                # Check if database exists
                result = conn.execute(
                    text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
                )
                if result.fetchone():
                    print(f"   ℹ️  Database '{db_name}' already exists\n")
                else:
                    conn.execute(text(f"CREATE DATABASE {db_name}"))
                    print(f"   ✅ Database '{db_name}' created\n")
        except Exception as e:
            print(f"   ❌ Failed to create database: {e}\n")
            return False
        
        # Now connect to the new database and create tables
        print("3️⃣  Creating tables...")
        target_db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        try:
            from app.database import Base, engine as app_engine
            from app.models.transport import Transport, User
            
            if app_engine:
                Base.metadata.create_all(bind=app_engine)
                print("   ✅ SQLAlchemy tables created\n")
            else:
                print("   ❌ Could not initialize engine\n")
                return False
        except Exception as e:
            print(f"   ⚠️  SQLAlchemy table creation: {e}\n")
        
        # Read and execute schema.sql
        print("4️⃣  Loading schema from schema.sql...")
        schema_file = Path(__file__).parent / "database" / "schema.sql"
        
        if schema_file.exists():
            try:
                with schema_file.open() as f:
                    schema_sql = f.read()
                
                engine_target = create_engine(target_db_url, echo=False)
                with engine_target.connect() as conn:
                    conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                    
                    # Split and execute each statement
                    statements = schema_sql.split(";")
                    for statement in statements:
                        stmt_clean = statement.strip()
                        if stmt_clean and not stmt_clean.startswith("--"):
                            try:
                                conn.execute(text(stmt_clean))
                            except Exception as e:
                                # Ignore duplicate table errors
                                if "already exists" not in str(e):
                                    print(f"   ⚠️  {e}")
                
                print("   ✅ Schema loaded from schema.sql\n")
            except Exception as e:
                print(f"   ⚠️  Could not load schema.sql: {e}\n")
        
        # Seed initial data if seed.sql exists
        print("5️⃣  Loading seed data...")
        seed_file = Path(__file__).parent / "database" / "seed.sql"
        
        if seed_file.exists():
            try:
                with seed_file.open() as f:
                    seed_sql = f.read()
                
                engine_target = create_engine(target_db_url, echo=False)
                with engine_target.connect() as conn:
                    conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                    
                    statements = seed_sql.split(";")
                    for statement in statements:
                        stmt_clean = statement.strip()
                        if stmt_clean and not stmt_clean.startswith("--"):
                            try:
                                conn.execute(text(stmt_clean))
                            except Exception as e:
                                # Ignore duplicate key errors
                                if "duplicate" not in str(e).lower():
                                    print(f"   ⚠️  {e}")
                
                print("   ✅ Seed data loaded\n")
            except Exception as e:
                print(f"   ℹ️  No seed data: {e}\n")
        
        print("✅ Database setup complete!\n")
        print("🚀 Next steps:")
        print("   1. Start backend: uvicorn app.main:app --reload --port 8001")
        print("   2. In another terminal: npm run dev (from frontend/)")
        print("   3. Open http://localhost:3001 in browser\n")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the project root directory\n")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}\n")
        return False

if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1)
