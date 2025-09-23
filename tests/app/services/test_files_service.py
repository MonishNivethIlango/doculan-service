import sys
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

# Patch DB connection before importing anything that transitively imports it
tracker_collection_mock = MagicMock()
tracker_collection_mock.find_one = AsyncMock()
sys.modules['auth_app.app.database.connection'] = MagicMock(
    db=MagicMock(),
    save_document_url=MagicMock(),
    tracker_collection=tracker_collection_mock
)

from app.services.files_service import FileService
from app.services.security_service import EncryptionService

class DummyFile:
    def __init__(self, filename, content):
        self.filename = filename
        self.content = content

    async def read(self):
        return self.content

class DummyStorage:
    def upload(self, *args, **kwargs):
        return "s3_url"

@pytest.mark.asyncio
@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
@patch.object(EncryptionService, "collection", create=True, new_callable=MagicMock)
async def test_files_upload_success(mock_collection, mock_s3_head_upload):
    mock_collection.find_one = AsyncMock(return_value={"encryption_email": "test@enc.com"})
    def not_found(*args, **kwargs):
        raise ClientError({"Error": {"Code": "404"}}, "head_object")
    mock_s3_head_upload.side_effect = not_found

    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    results = await service.files_upload(
        "user@example.com", "uploader@example.com", "Uploader Name", files
    )
    assert results[0]["status"] == "uploaded"

@pytest.mark.asyncio
@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
@patch.object(EncryptionService, "collection", create=True, new_callable=MagicMock)
async def test_files_upload_existing_file(mock_collection, mock_s3_head_upload):
    mock_collection.find_one = AsyncMock(return_value={"encryption_email": "test@enc.com"})
    mock_s3_head_upload.return_value = True
    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    with pytest.raises(HTTPException) as exc:
        await service.files_upload(
            "user@example.com", "uploader@example.com", "Uploader Name", files
        )
    assert exc.value.status_code == 409

@pytest.mark.asyncio
@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
@patch.object(EncryptionService, "collection", create=True, new_callable=MagicMock)
async def test_files_upload_overwrite(mock_collection, mock_s3_head_upload):
    mock_collection.find_one = AsyncMock(return_value={"encryption_email": "test@enc.com"})
    mock_s3_head_upload.return_value = True
    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    results = await service.files_upload(
        "user@example.com", "uploader@example.com", "Uploader Name", files, overwrite=True
    )
    assert results[0]["status"] == "uploaded"

@pytest.mark.asyncio
@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
@patch.object(EncryptionService, "collection", create=True, new_callable=MagicMock)
async def test_files_upload_s3_error(mock_collection, mock_s3_head_upload):
    mock_collection.find_one = AsyncMock(return_value={"encryption_email": "test@enc.com"})
    mock_s3_head_upload.side_effect = ClientError({"Error": {"Code": "500"}}, "upload")
    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    with pytest.raises(HTTPException) as exc:
        await service.files_upload(
            "user@example.com", "uploader@example.com", "Uploader Name", files
        )
    assert exc.value.status_code == 500

@pytest.mark.asyncio
@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
@patch.object(EncryptionService, "collection", create=True, new_callable=MagicMock)
async def test_files_upload_storage_error(mock_collection, mock_s3_head_upload):
    mock_collection.find_one = AsyncMock(return_value={"encryption_email": "test@enc.com"})
    mock_s3_head_upload.side_effect = Exception("Storage error")
    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    with pytest.raises(Exception) as exc:
        await service.files_upload(
            "user@example.com", "uploader@example.com", "Uploader Name", files
        )
    assert "Storage error" in str(exc.value)