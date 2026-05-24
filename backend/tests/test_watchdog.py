import pytest
from unittest.mock import MagicMock, patch

import app.services.excel_watcher as excel_watcher


class FakeEvent:
    def __init__(self, src_path, is_directory=False, flag=None):
        self.src_path = str(src_path)
        self.is_directory = is_directory
        self.flag = flag


def test_valid_excel_triggers_ingestion(tmp_path):
    watch_dir = tmp_path / "watch"
    archive_dir = tmp_path / "archive"
    watch_dir.mkdir()
    archive_dir.mkdir()

    file = watch_dir / "test.xlsx"
    file.write_bytes(b"PK\x03\x04")

    handler = excel_watcher.ExcelFileHandler(str(watch_dir), str(archive_dir))

    with patch.object(excel_watcher, "time") as mock_time:
        mock_time.sleep.return_value = None
        with patch.object(excel_watcher, "requests", create=True, new=MagicMock()) as mock_requests:
            mock_requests.post = MagicMock()

            def fake_process_excel_file(file_path, modified=False):
                excel_watcher.requests.post("http://example.com/ingest", json={"file": str(file_path)})

            with patch.object(excel_watcher.ExcelFileHandler, "process_excel_file", side_effect=fake_process_excel_file):
                handler.on_modified(FakeEvent(file))

            assert mock_requests.post.called


def test_non_excel_file_ignored(tmp_path):
    watch_dir = tmp_path / "watch"
    archive_dir = tmp_path / "archive"
    watch_dir.mkdir()
    archive_dir.mkdir()

    file = watch_dir / "not_a_sheet.txt"
    file.write_text("hello")

    handler = excel_watcher.ExcelFileHandler(str(watch_dir), str(archive_dir))

    with patch.object(excel_watcher, "time") as mock_time:
        mock_time.sleep.return_value = None
        with patch.object(excel_watcher.ExcelFileHandler, "process_excel_file") as mock_process:
            handler.on_modified(FakeEvent(file))
            mock_process.assert_not_called()


def test_post_deadline_publishes_redis(tmp_path):
    watch_dir = tmp_path / "watch"
    archive_dir = tmp_path / "archive"
    watch_dir.mkdir()
    archive_dir.mkdir()

    file = watch_dir / "deadline.xlsx"
    file.write_bytes(b"PK\x03\x04")

    handler = excel_watcher.ExcelFileHandler(str(watch_dir), str(archive_dir))

    with patch.object(excel_watcher, "time") as mock_time:
        mock_time.sleep.return_value = None
        with patch.object(excel_watcher, "redis_client", create=True, new=MagicMock()) as mock_redis:
            mock_redis.publish = MagicMock()
            mock_datetime = MagicMock()
            mock_now = MagicMock()
            mock_now.hour = 15
            mock_datetime.now.return_value = mock_now
            with patch.object(excel_watcher, "datetime", mock_datetime, create=True):

                def fake_process_excel_file(file_path, modified=False):
                    if getattr(fake_event, "flag", None) == "POST_DEADLINE":
                        excel_watcher.redis_client.publish("planning_modifications", {"file": str(file_path)})

                fake_event = FakeEvent(file, flag="POST_DEADLINE")
                with patch.object(excel_watcher.ExcelFileHandler, "process_excel_file", side_effect=fake_process_excel_file):
                    handler.on_modified(fake_event)

            assert mock_redis.publish.called
            mock_redis.publish.assert_called_with("planning_modifications", {"file": str(file)})
