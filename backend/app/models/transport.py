from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.database import Base
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# SQLAlchemy Models
class Transport(Base):
    __tablename__ = "transports"

    id = Column(Integer, primary_key=True, index=True)
    driver = Column(String, nullable=False)
    vehicle = Column(String, nullable=False)
    start_location = Column(String, nullable=False)
    end_location = Column(String, nullable=False)
    distance_km = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Pydantic Schemas
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
    created_at: datetime

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None