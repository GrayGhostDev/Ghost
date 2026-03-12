"""Tests for src/ghost/storage.py"""

import io
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.ghost.storage import (
    FileType,
    FileValidator,
    LocalStorageProvider,
    S3StorageProvider,
    StorageManager,
    StorageProvider,
)


# ──────────────────────────────────────────────
# FileValidator
# ──────────────────────────────────────────────

class TestFileValidatorGetFileType:
    def test_image_by_extension(self):
        assert FileValidator.get_file_type("photo.jpg") == FileType.IMAGE
        assert FileValidator.get_file_type("icon.png") == FileType.IMAGE

    def test_video_by_extension(self):
        assert FileValidator.get_file_type("clip.mp4") == FileType.VIDEO

    def test_document_by_extension(self):
        assert FileValidator.get_file_type("report.pdf") == FileType.DOCUMENT

    def test_archive_by_extension(self):
        assert FileValidator.get_file_type("backup.zip") == FileType.ARCHIVE

    def test_code_by_extension(self):
        assert FileValidator.get_file_type("app.py") == FileType.CODE

    def test_unknown_extension(self):
        assert FileValidator.get_file_type("file.xyz") == FileType.OTHER

    def test_mime_type_fallback(self):
        assert FileValidator.get_file_type("noext", content_type="image/jpeg") == FileType.IMAGE

    def test_mime_type_video(self):
        assert FileValidator.get_file_type("noext", content_type="video/mp4") == FileType.VIDEO


class TestFileValidatorExtension:
    def test_allowed(self):
        assert FileValidator.validate_extension("photo.jpg", [FileType.IMAGE]) is True

    def test_not_allowed(self):
        assert FileValidator.validate_extension("photo.jpg", [FileType.VIDEO]) is False

    def test_no_filter(self):
        assert FileValidator.validate_extension("anything.xyz", None) is True


class TestFileValidatorSize:
    def test_valid_size(self):
        assert FileValidator.validate_size(100, max_size=1000) is True

    def test_too_large(self):
        assert FileValidator.validate_size(2000, max_size=1000) is False

    def test_zero_size(self):
        assert FileValidator.validate_size(0) is False

    def test_no_max(self):
        assert FileValidator.validate_size(999999) is True


# ──────────────────────────────────────────────
# LocalStorageProvider
# ──────────────────────────────────────────────

class TestLocalStorageProvider:
    def test_save_and_get(self, tmp_storage):
        data = io.BytesIO(b"hello world")
        uploaded = tmp_storage.save(data, "test.txt")

        assert uploaded.original_name == "test.txt"
        assert uploaded.size == 11
        assert uploaded.file_type == FileType.DOCUMENT  # .txt is in DOCUMENT set
        assert uploaded.provider == StorageProvider.LOCAL

        content = tmp_storage.get(uploaded.path)
        assert content == b"hello world"

    def test_save_image(self, tmp_storage):
        data = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        uploaded = tmp_storage.save(data, "photo.png")
        assert uploaded.file_type == FileType.IMAGE

    def test_delete(self, tmp_storage):
        data = io.BytesIO(b"delete me")
        uploaded = tmp_storage.save(data, "delete.txt")

        assert tmp_storage.delete(uploaded.path) is True
        assert tmp_storage.get(uploaded.path) is None

    def test_delete_nonexistent(self, tmp_storage):
        assert tmp_storage.delete("/nonexistent/file.txt") is False

    def test_get_nonexistent(self, tmp_storage):
        assert tmp_storage.get("/nonexistent/file.txt") is None

    def test_uploaded_file_to_dict(self, tmp_storage):
        data = io.BytesIO(b"test")
        uploaded = tmp_storage.save(data, "file.txt")
        d = uploaded.to_dict()
        assert d["original_name"] == "file.txt"
        assert "id" in d
        assert d["provider"] == "local"

    def test_metadata_to_dict(self, tmp_storage):
        data = io.BytesIO(b"test")
        uploaded = tmp_storage.save(data, "file.txt")
        md = uploaded.metadata.to_dict()
        assert md["filename"] == "file.txt"
        assert md["size"] == 4
        assert "hash" in md


# ──────────────────────────────────────────────
# S3StorageProvider (mocked boto3)
# ──────────────────────────────────────────────

class TestS3StorageProvider:
    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 so S3StorageProvider can be instantiated without the real package."""
        mock_boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            self._mock_client = mock_boto3.client.return_value
            yield

    def _make_provider(self):
        provider = S3StorageProvider(
            bucket="test-bucket",
            region="us-east-1",
            access_key="AKID",
            secret_key="SECRET",
        )
        provider.client = self._mock_client
        return provider

    def test_save(self):
        provider = self._make_provider()
        data = io.BytesIO(b"s3 content")
        uploaded = provider.save(data, "report.pdf")

        assert uploaded.provider == StorageProvider.S3
        assert uploaded.original_name == "report.pdf"
        assert uploaded.size == 10
        provider.client.put_object.assert_called_once()

    def test_delete(self):
        provider = self._make_provider()
        assert provider.delete("some/key.txt") is True
        provider.client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="some/key.txt"
        )

    def test_delete_failure(self):
        provider = self._make_provider()
        provider.client.delete_object.side_effect = Exception("AWS error")
        assert provider.delete("some/key.txt") is False

    def test_get(self):
        provider = self._make_provider()
        body_mock = MagicMock()
        body_mock.read.return_value = b"content"
        provider.client.get_object.return_value = {"Body": body_mock}

        content = provider.get("some/key.txt")
        assert content == b"content"

    def test_get_failure(self):
        provider = self._make_provider()
        provider.client.get_object.side_effect = Exception("not found")
        assert provider.get("missing.txt") is None


# ──────────────────────────────────────────────
# StorageManager
# ──────────────────────────────────────────────

class TestStorageManager:
    def test_local_upload(self, tmp_path):
        mgr = StorageManager(
            provider=StorageProvider.LOCAL,
            config={"base_path": str(tmp_path / "uploads")},
        )
        data = io.BytesIO(b"content here")
        uploaded = mgr.upload(data, "doc.txt")
        assert uploaded.original_name == "doc.txt"

    def test_upload_extension_rejected(self, tmp_path):
        mgr = StorageManager(
            provider=StorageProvider.LOCAL,
            config={"base_path": str(tmp_path / "uploads")},
        )
        data = io.BytesIO(b"content")
        with pytest.raises(ValueError, match="File type not allowed"):
            mgr.upload(data, "photo.jpg", allowed_types=[FileType.DOCUMENT])

    def test_upload_size_rejected(self, tmp_path):
        mgr = StorageManager(
            provider=StorageProvider.LOCAL,
            config={"base_path": str(tmp_path / "uploads")},
        )
        data = io.BytesIO(b"x" * 100)
        with pytest.raises(ValueError, match="File too large"):
            mgr.upload(data, "file.txt", max_size=10)

    def test_delete_via_manager(self, tmp_path):
        mgr = StorageManager(
            provider=StorageProvider.LOCAL,
            config={"base_path": str(tmp_path / "uploads")},
        )
        data = io.BytesIO(b"to delete")
        uploaded = mgr.upload(data, "del.txt")
        assert mgr.delete(uploaded.path) is True

    def test_get_via_manager(self, tmp_path):
        mgr = StorageManager(
            provider=StorageProvider.LOCAL,
            config={"base_path": str(tmp_path / "uploads")},
        )
        data = io.BytesIO(b"readable")
        uploaded = mgr.upload(data, "read.txt")
        assert mgr.get(uploaded.path) == b"readable"
