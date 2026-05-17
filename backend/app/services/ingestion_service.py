"""
Ingestion Service for CofICab Platform
Handles Excel file processing and database insertion
"""

import pandas as pd
from sqlalchemy.orm import Session
from app.models.livraison import Livraison
from app.models.ingestion_log import IngestionLog
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class IngestionService:
    """Service for processing Excel files and inserting data into database"""

    def __init__(self, db: Session):
        self.db = db

    def ingest_excel_file(self, file_path: str, file_name: str = None) -> dict:
        """
        Read Excel file and insert livraison data into database.

        Expected Excel columns: driver, vehicle, start, end, distance
        Optional columns: status, priority, notes

        Returns dict with processing results.
        """
        if not file_name:
            file_name = file_path.split('/')[-1].split('\\')[-1]

        result = {
            "file_name": file_name,
            "status": "processing",
            "total_rows": 0,
            "inserted_rows": 0,
            "error_count": 0,
            "errors": []
        }

        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            result["total_rows"] = len(df)

            # Validate required columns
            required_columns = ['driver', 'vehicle', 'start', 'end', 'distance']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                result["status"] = "failed"
                result["errors"].append(f"Missing required columns: {missing_columns}")
                return result

            # Process each row
            livraison_objects = []

            for index, row in df.iterrows():
                try:
                    # Extract and validate data
                    livraison_data = {
                        'driver': str(row['driver']).strip(),
                        'vehicle': str(row['vehicle']).strip(),
                        'start_location': str(row['start']).strip(),
                        'end_location': str(row['end']).strip(),
                        'distance_km': float(row['distance']),
                        'status': str(row.get('status', 'pending')).strip() or 'pending',
                        'priority': str(row.get('priority', 'normal')).strip() or 'normal',
                        'notes': str(row.get('notes', '')).strip() if pd.notna(row.get('notes')) else None
                    }

                    # Basic validation
                    if not all([
                        livraison_data['driver'],
                        livraison_data['vehicle'],
                        livraison_data['start_location'],
                        livraison_data['end_location']
                    ]):
                        raise ValueError("Missing required field values")

                    if livraison_data['distance_km'] <= 0:
                        raise ValueError("Distance must be positive")

                    # Create livraison object
                    livraison = Livraison(**livraison_data)
                    livraison_objects.append(livraison)
                    result["inserted_rows"] += 1

                except Exception as e:
                    result["error_count"] += 1
                    error_msg = f"Row {index + 1}: {str(e)}"
                    result["errors"].append(error_msg)
                    logger.warning(error_msg)
                    continue

            # Bulk insert all valid records
            if livraison_objects:
                self.db.add_all(livraison_objects)
                self.db.commit()

            # Determine final status
            if result["inserted_rows"] == result["total_rows"] and result["error_count"] == 0:
                result["status"] = "success"
            elif result["inserted_rows"] > 0:
                result["status"] = "partial"
            else:
                result["status"] = "failed"

            return result

        except Exception as e:
            result["status"] = "failed"
            result["errors"].append(f"File processing error: {str(e)}")
            return result

    def create_ingestion_log(self, file_path: str, result: dict) -> IngestionLog:
        """Create an ingestion log entry"""
        log_entry = IngestionLog(
            file_name=result["file_name"],
            file_path=file_path,
            status=result["status"],
            inserted_rows=result["inserted_rows"],
            total_rows=result["total_rows"],
            error_message="; ".join(result["errors"]) if result["errors"] else None,
            processed_at=datetime.now()
        )

        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)

        return log_entry

    def get_ingestion_history(self, limit: int = 50) -> list:
        """Get recent ingestion history"""
        logs = self.db.query(IngestionLog).order_by(
            IngestionLog.import_date.desc()
        ).limit(limit).all()

        return [{
            "id": log.id,
            "file_name": log.file_name,
            "import_date": log.import_date.isoformat(),
            "status": log.status,
            "inserted_rows": log.inserted_rows,
            "total_rows": log.total_rows,
            "error_message": log.error_message
        } for log in logs]