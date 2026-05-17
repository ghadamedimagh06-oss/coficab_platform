"""
Ingestion Log Model for CofICab Platform
Tracks Excel file import operations and their results
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.database import Base

class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    import_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), nullable=False)  # success, failed, partial
    inserted_rows = Column(Integer, default=0)
    total_rows = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    archived_path = Column(String(500), nullable=True)

    def __repr__(self):
        return f"<IngestionLog(id={self.id}, file='{self.file_name}', status='{self.status}', rows={self.inserted_rows})>"