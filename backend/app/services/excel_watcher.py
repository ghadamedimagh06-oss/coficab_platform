"""
Excel Watcher Service for CofICab Platform
Automatically monitors Excel files and processes them into PostgreSQL
"""

import os
import time
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pandas as pd
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.livraison import Livraison
from app.models.ingestion_log import IngestionLog
from app.models.planning_version import PlanningVersion
from app.services.planning_service import PlanningService
from datetime import datetime, date

last_detection_summary = {
    "today": None,
    "j_plus_1": None,
    "detected": [],
    "ignored": [],
    "planning_id": None,
    "status": None,
}

class ExcelFileHandler(FileSystemEventHandler):
    """Handles file system events for Excel files"""

    def __init__(self, watch_path: str, archive_path: str):
        self.watch_path = Path(watch_path)
        self.archive_path = Path(archive_path)
        self.processed_files = set()  # Track processed files to avoid duplicates

        # Ensure archive directory exists
        self.archive_path.mkdir(parents=True, exist_ok=True)

        print(f"📁 Monitoring: {self.watch_path}")
        print(f"📦 Archive: {self.archive_path}")

    def on_created(self, event):
        """Called when a new file is created"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process .xlsx files
        if file_path.suffix.lower() != '.xlsx':
            return

        # Avoid processing files that are still being written
        time.sleep(1)  # Small delay to ensure file is fully written

        # Check if file is still being modified
        initial_size = file_path.stat().st_size
        time.sleep(0.5)
        final_size = file_path.stat().st_size

        if initial_size != final_size:
            print(f"⏳ File still being written: {file_path.name}")
            return

        # Process the Excel file
        self.process_excel_file(file_path)

    def on_modified(self, event):
        """Called when an existing file is modified"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        if file_path.suffix.lower() != '.xlsx':
            return

        time.sleep(1)
        initial_size = file_path.stat().st_size
        time.sleep(0.5)
        final_size = file_path.stat().st_size

        if initial_size != final_size:
            print(f"⏳ File still being written: {file_path.name}")
            return

        self.process_excel_file(file_path, modified=True)

    def process_excel_file(self, file_path: Path, modified: bool = False):
        """Process an Excel file and insert data into database"""
        file_name = file_path.name

        print(f"\n📥 File detected: {file_name}")

        # Create database session
        db = SessionLocal()

        try:
            # Create initial log entry
            log_entry = IngestionLog(
                file_name=file_name,
                file_path=str(file_path),
                status="processing",
                total_rows=0,
                inserted_rows=0
            )
            db.add(log_entry)
            db.commit()

            # Read Excel file
            try:
                df = pd.read_excel(file_path)
                total_rows = len(df)
                print(f"📊 Rows extracted: {total_rows}")

                # Update log with total rows
                log_entry.total_rows = total_rows
                db.commit()

            except Exception as e:
                error_msg = f"Failed to read Excel file: {str(e)}"
                print(f"❌ {error_msg}")
                log_entry.status = "failed"
                log_entry.error_message = error_msg
                db.commit()
                db.close()
                return

            # Validate required columns
            required_columns = ['driver', 'vehicle', 'start', 'end', 'distance']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                error_msg = f"Missing required columns: {missing_columns}"
                print(f"❌ {error_msg}")
                log_entry.status = "failed"
                log_entry.error_message = error_msg
                db.commit()
                db.close()
                return

            # Process and insert data
            inserted_count = 0
            error_count = 0

            livraison_objects = []

            for index, row in df.iterrows():
                try:
                    # Clean and validate data
                    driver = str(row['driver']).strip()
                    vehicle = str(row['vehicle']).strip()
                    start_location = str(row['start']).strip()
                    end_location = str(row['end']).strip()
                    distance_km = float(row['distance'])

                    # Basic validation
                    if not all([driver, vehicle, start_location, end_location]):
                        raise ValueError("Missing required field values")

                    if distance_km <= 0:
                        raise ValueError("Distance must be positive")

                    # Create livraison object
                    livraison = Livraison(
                        driver=driver,
                        vehicle=vehicle,
                        start_location=start_location,
                        end_location=end_location,
                        distance_km=distance_km,
                        status="pending"
                    )

                    livraison_objects.append(livraison)
                    inserted_count += 1

                except Exception as e:
                    error_count += 1
                    print(f"⚠️  Row {index + 1} error: {str(e)}")
                    continue

            # Bulk insert all valid records
            if livraison_objects:
                db.add_all(livraison_objects)
                db.commit()
                print(f"✅ Database updated: {inserted_count} records inserted")

            # Update log entry
            log_entry.inserted_rows = inserted_count
            log_entry.processed_at = datetime.now()

            if inserted_count == total_rows and error_count == 0:
                log_entry.status = "success"
                print("✅ Import completed successfully")
            elif inserted_count > 0:
                log_entry.status = "partial"
                log_entry.error_message = f"Inserted {inserted_count}/{total_rows} rows, {error_count} errors"
                print(f"⚠️  Partial import: {inserted_count}/{total_rows} rows inserted")
            else:
                log_entry.status = "failed"
                log_entry.error_message = f"No valid rows inserted. {error_count} errors"
                print("❌ Import failed: No valid data inserted")

            db.commit()

            # Planning integration after successful ingestion
            if log_entry.status in ["success", "partial"]:
                try:
                    service = PlanningService(db)
                    if modified:
                        plan_data = service.parse_weekly_planning(str(file_path))
                        week = plan_data["week"]
                        planning = db.query(PlanningVersion).filter(
                            PlanningVersion.week == week,
                            PlanningVersion.status == "VALIDATED"
                        ).order_by(PlanningVersion.id.desc()).first()

                        if planning:
                            result = service.compare_validated_planning_with_excel(planning, str(file_path))
                            print(f"[WATCHDOG] Today: {date.today().strftime('%A')}")
                            print(f"[WATCHDOG] Target J+1: {result.get('j_plus_1')}")
                            print(f"[WATCHDOG] Detected changes: {result.get('diff_count')}")
                            print(f"[WATCHDOG] Ignored count: {len(result.get('ignored', []))}")

                            last_detection_summary.update({
                                "today": date.today().strftime('%A'),
                                "j_plus_1": result.get('j_plus_1'),
                                "detected": [
                                    {
                                        "row": diff["row_number"],
                                        "field": diff["field_name"],
                                        "old": diff["old_value"],
                                        "new": diff["new_value"]
                                    }
                                    for diff in result.get("diffs", [])
                                    if diff.get("is_j_plus_1")
                                ],
                                "ignored": [
                                    {
                                        "row": diff["row_number"],
                                        "reason": diff.get("ignored_reason")
                                    }
                                    for diff in result.get("diffs", [])
                                    if diff.get("ignored_reason")
                                ],
                                "planning_id": planning.id,
                                "status": planning.status,
                            })
                        else:
                            planning = service.create_planning_from_excel(str(file_path), created_by=0)
                            last_detection_summary.update({
                                "today": date.today().strftime('%A'),
                                "j_plus_1": service._next_j_plus_1_day(),
                                "detected": [],
                                "ignored": [],
                                "planning_id": planning.id,
                                "status": planning.status,
                            })
                    else:
                        planning = service.create_planning_from_excel(str(file_path), created_by=0)
                        last_detection_summary.update({
                            "today": date.today().strftime('%A'),
                            "j_plus_1": service._next_j_plus_1_day(),
                            "detected": [],
                            "ignored": [],
                            "planning_id": planning.id,
                            "status": planning.status,
                        })
                except Exception as e:
                    print(f"❌ Planning integration error: {str(e)}")

            # Archive the file if processing was successful
            if log_entry.status in ["success", "partial"]:
                self.archive_file(file_path, log_entry)
            else:
                print("❌ File not archived due to import failure")

        except Exception as e:
            error_msg = f"Unexpected error during processing: {str(e)}"
            print(f"❌ {error_msg}")

            # Update log with error
            try:
                log_entry.status = "failed"
                log_entry.error_message = error_msg
                db.commit()
            except:
                pass

        finally:
            db.close()

    def archive_file(self, file_path: Path, log_entry: IngestionLog):
        """Move processed file to archive directory"""
        try:
            # Create archive filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archived_name = f"{timestamp}_{file_path.name}"
            archived_path = self.archive_path / archived_name

            # Move file
            shutil.move(str(file_path), str(archived_path))

            # Update log with archive path
            db = SessionLocal()
            try:
                log_entry.archived_path = str(archived_path)
                db.commit()
                print(f"📦 File archived: {archived_name}")
            finally:
                db.close()

        except Exception as e:
            print(f"❌ Failed to archive file: {str(e)}")

class ExcelWatcherService:
    """Main service for monitoring Excel files"""

    def __init__(self, watch_path: str, archive_path: str):
        self.watch_path = Path(watch_path)
        self.archive_path = Path(archive_path)
        self.observer = None
        self.event_handler = None

    def start(self):
        """Start the file monitoring service"""
        print("🚀 Starting Excel Watcher Service...")

        # Ensure watch directory exists
        self.watch_path.mkdir(parents=True, exist_ok=True)

        # Create event handler
        self.event_handler = ExcelFileHandler(str(self.watch_path), str(self.archive_path))

        # Create observer
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.watch_path), recursive=False)

        # Start monitoring
        self.observer.start()
        print("✅ Excel Watcher Service started successfully")
        print(f"📁 Monitoring directory: {self.watch_path}")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the file monitoring service"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("🛑 Excel Watcher Service stopped")

def main():
    """Main entry point for the Excel watcher service"""

    # Configuration
    WATCH_PATH = r"C:\Users\USER\OneDrive\Desktop\coficab\weekly planning"
    ARCHIVE_PATH = r"C:\Users\USER\OneDrive\Desktop\coficab\archive"

    print("🔧 CofICab Excel Watcher Service")
    print("=" * 50)

    # Create service instance
    watcher = ExcelWatcherService(WATCH_PATH, ARCHIVE_PATH)

    try:
        watcher.start()
    except KeyboardInterrupt:
        print("\n🛑 Service interrupted by user")
    except Exception as e:
        print(f"❌ Service error: {str(e)}")
    finally:
        watcher.stop()

if __name__ == "__main__":
    main()