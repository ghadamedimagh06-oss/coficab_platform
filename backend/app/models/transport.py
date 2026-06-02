"""Pydantic schemas for auth/transport (SQLAlchemy models moved to user.py, camion.py, etc.)"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# Auth Pydantic schemas
class UserCreate(BaseModel):
    username: str
    email: str = ""
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    date_creation: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    role: Optional[str] = None


class TokenData(BaseModel):
    username: Optional[str] = None


# Transport Pydantic schemas (legacy — kept for any route that still uses them)
class TransportBase(BaseModel):
    driver: str
    vehicle: str
    start_location: str
    end_location: str
    distance_km: float


class TransportCreate(TransportBase):
    pass


class TransportResponse(TransportBase):
    id: int

    class Config:
        from_attributes = True
