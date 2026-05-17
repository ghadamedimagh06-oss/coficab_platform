#!/usr/bin/env python3
"""
Seed script to create initial data
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.services.auth_service import AuthService
from app.models.transport import UserCreate

def seed_database():
    """Create initial user and data"""
    # Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        auth_service = AuthService(db)

        # Create default admin user
        try:
            user_data = UserCreate(username="admin", password="admin123")
            user = auth_service.create_user(user_data)
            print(f"Created user: {user.username}")
        except Exception as e:
            print(f"User already exists or error: {e}")

        print("Database seeded successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    seed_database()