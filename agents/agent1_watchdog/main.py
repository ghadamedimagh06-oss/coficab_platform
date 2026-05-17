import os
import time
import json
import requests
import pandas as pd
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WATCH_DIRECTORY = r"C:\Users\USER\OneDrive\Desktop\coficab\DB"
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")


class ExcelFileHandler(FileSystemEventHandler):

    def on_created(self, event):
        if not event.is_directory:
            filename = os.path.basename(event.src_path)
            if "weekly" in filename.lower() and filename.endswith(('.xlsx', '.xls')):
                logger.info(f"[WATCHDOG] Weekly planning detected: {filename}")
                time.sleep(1)
                self.process_excel(event.src_path)
            else:
                logger.info(f"[WATCHDOG] Ignored (not weekly): {filename}")

    def process_excel(self, file_path):
        try:
            # ← header fi row 3 = index 2, sheet Planning
            df = pd.read_excel(file_path, header=2, sheet_name="Planning")

            # ← temshi rows w columns farigha
            df = df.dropna(how='all')
            df = df.fillna("")
            df.columns = df.columns.str.strip()

            # ← rename columns
            df = df.rename(columns={
                'Delivery Day'      : 'delivery_day',
                'N°'                : 'numero',
                'Customer'          : 'customer',
                'ETD'               : 'etd',
                'Position Nbr'      : 'position_nbr',
                'Status'            : 'status',
                'Comments'          : 'comments',
                'EDI'               : 'edi',
                'Priority'          : 'priority',
                'Pallet weight'     : 'pallet_weight',
                'Gross weight'      : 'gross_weight',
                'Total Gross weight': 'total_gross_weight'
            })

            # ← temshi rows bla customer
            df = df[df['customer'] != '']

            # ← fill merged cells mte3 delivery_day
            df['delivery_day'] = df['delivery_day'].replace('', None).ffill()

            # ← temshi spaces zeyda mel delivery_day
            df['delivery_day'] = df['delivery_day'].str.strip()

            logger.info(f"[WATCHDOG] ✅ Loaded: {len(df)} deliveries")
            logger.info(f"[WATCHDOG] Days found: {df['delivery_day'].unique()}")

            # ← convert kol time/datetime objects automatiquement
            data = json.loads(df.to_json(orient="records", force_ascii=False))

            response = requests.post(
                f"{BACKEND_API_URL}/api/ingestion/data",
                json={
                    "filename": os.path.basename(file_path),
                    "rows": data
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"[WATCHDOG] ✅ Sent {len(data)} rows to backend successfully")
            else:
                logger.error(f"[WATCHDOG] ❌ Failed: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"[WATCHDOG] ❌ Error: {e}")


def start_watchdog():
    if not os.path.exists(WATCH_DIRECTORY):
        logger.error(f"[WATCHDOG] ❌ Folder not found: {WATCH_DIRECTORY}")
        return

    observer = Observer()
    observer.schedule(ExcelFileHandler(), WATCH_DIRECTORY, recursive=False)
    observer.start()
    logger.info(f"[WATCHDOG] ✅ Watching: {WATCH_DIRECTORY}")
    logger.info(f"[WATCHDOG] Waiting for 'weekly' Excel files...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("[WATCHDOG] Stopped")
    observer.join()


if __name__ == "__main__":
    start_watchdog()