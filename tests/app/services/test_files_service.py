from unittest.mock import AsyncMock, patch, MagicMock
from app.services.files_service import FileService
from botocore.exceptions import ClientError
from fastapi import HTTPException
import pytest

class DummyFile:
    def __init__(self, filename, content):
        self.filename = filename
        self.content = content

    async def read(self):
        return self.content

class DummyStorage:
    def upload(self, *args, **kwargs):
        return "s3_url"

@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
def test_files_upload_success(mock_s3_head_upload):
    # Simulate file does NOT exist by raising ClientError with code "404"
    def not_found(*args, **kwargs):
        raise ClientError({"Error": {"Code": "404"}}, "head_object")
    mock_s3_head_upload.side_effect = not_found

    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    import asyncio
    results = asyncio.run(service.files_upload(
        "user@example.com", "uploader@example.com", "Uploader Name", files
    ))
    assert results[0]["status"] == "uploaded"
    
@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
def test_files_upload_existing_file(mock_s3_head_upload):
    mock_s3_head_upload.return_value = True
    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    import asyncio
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.files_upload(
            "user@example.com", "uploader@example.com", "Uploader Name", files
        ))
    assert exc.value.status_code == 409

@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
def test_files_upload_overwrite(mock_s3_head_upload):
    mock_s3_head_upload.return_value = True
    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    import asyncio
    results = asyncio.run(service.files_upload(
        "user@example.com", "uploader@example.com", "Uploader Name", files, overwrite=True
    ))
    assert results[0]["status"] == "uploaded"

@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
def test_files_upload_s3_error(mock_s3_head_upload):
    mock_s3_head_upload.side_effect = ClientError({"Error": {"Code": "500"}}, "upload")
    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    import asyncio
    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.files_upload(
            "user@example.com", "uploader@example.com", "Uploader Name", files
        ))
    assert exc.value.status_code == 500

@patch("app.services.files_service.s3_head_upload", new_callable=AsyncMock)
def test_files_upload_storage_error(mock_s3_head_upload):
    mock_s3_head_upload.side_effect = Exception("Storage error")
    service = FileService(DummyStorage())
    files = [DummyFile("file1.txt", b"hello")]
    import asyncio
    with pytest.raises(Exception) as exc:
        asyncio.run(service.files_upload(
            "user@example.com", "uploader@example.com", "Uploader Name", files
        ))
    assert "Storage error" in str(exc.value)