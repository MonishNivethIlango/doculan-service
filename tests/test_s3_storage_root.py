import pytest
from unittest.mock import patch, MagicMock, Mock
from DataAccessLayer.storage.s3_storage import S3Storage
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException
import io

@pytest.fixture
def s3_storage():
    return S3Storage(bucket_name="test-bucket")

@pytest.fixture
def email():
    return "user@example.com"

@pytest.fixture
def document_id():
    return "doc-123"

@pytest.fixture
def file_obj():
    file = io.BytesIO(b"test content")
    upload = UploadFile(file=file, filename="test.pdf")
    upload.content_type = "application/pdf"
    return upload

def test_init_sets_bucket_name():
    s = S3Storage("bucket1")
    assert s.bucket_name == "bucket1"

def test_get_metadata_key_and_pdf_key(s3_storage, email, document_id):
    assert s3_storage._get_metadata_key(email, document_id) == f"{email}/files/{document_id}.json"
    assert s3_storage._get_pdf_key(email, "file.pdf") == f"{email}/files/file.pdf"
    assert s3_storage._get_metadata_key(email, document_id, "folder") == f"{email}/files/folder/{document_id}.json"
    assert s3_storage._get_pdf_key(email, "file.pdf", "folder") == f"{email}/files/folder/file.pdf"

@patch("DataAccessLayer.storage.s3_storage.s3_client")
def test_get_index_entry_found(mock_s3, s3_storage, email, document_id):
    mock_s3.get_object.return_value = {"Body": io.BytesIO(b'{"doc-123": {"meta": 1}}')}
    result = s3_storage._get_index_entry(email, document_id)
    assert result == {"meta": 1}

@patch("DataAccessLayer.storage.s3_storage.s3_client")
def test_get_index_entry_no_such_key(mock_s3, s3_storage, email, document_id):
    # Simulate NoSuchKey by raising ClientError with code 'NoSuchKey'
    from botocore.exceptions import ClientError
    error_response = {"Error": {"Code": "NoSuchKey"}}
    mock_s3.get_object.side_effect = ClientError(error_response, "get_object")
    result = s3_storage._get_index_entry(email, document_id)
    assert result == {}

@patch("DataAccessLayer.storage.s3_storage.s3_client")
def test_get_index_entry_other_exception(mock_s3, s3_storage, email, document_id):
    mock_s3.get_object.side_effect = Exception("fail")
    result = s3_storage._get_index_entry(email, document_id)
    assert result == {}

@patch("DataAccessLayer.storage.s3_storage.s3_client")
@patch("DataAccessLayer.storage.s3_storage.AESCipher")
@patch("DataAccessLayer.storage.s3_storage.config")
def test_upload_file_success(mock_config, mock_cipher, mock_s3, s3_storage, email, document_id, file_obj):
    mock_config.KMS_KEY_ID = "kms-key"
    mock_cipher.return_value.encrypt.return_value = b"encrypted"
    mock_s3.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "head_object")
    mock_s3.get_object.side_effect = mock_s3.exceptions.NoSuchKey
    mock_s3.put_object.return_value = None
    result = s3_storage.upload_file(email, document_id, file_obj)
    assert result["uploaded"] is True
    assert result["document_id"] == document_id
    assert "pdf" in result["s3_keys"]
    assert "metadata" in result["s3_keys"]

@patch("DataAccessLayer.storage.s3_storage.s3_client")
def test_upload_file_no_filename(mock_s3, s3_storage, email, document_id):
    file = io.BytesIO(b"test")
    upload = UploadFile(file=file, filename="")
    upload.content_type = "application/pdf"
    with pytest.raises(ValueError):
        s3_storage.upload_file(email, document_id, upload)

@patch("DataAccessLayer.storage.s3_storage.s3_client")
def test_upload_file_file_exists_no_overwrite(mock_s3, s3_storage, email, document_id, file_obj):
    mock_s3.head_object.return_value = True
    with pytest.raises(HTTPException) as exc:
        s3_storage.upload_file(email, document_id, file_obj, overwrite=False)
    assert exc.value.status_code == 409

@patch("DataAccessLayer.storage.s3_storage.s3_client")
def test_upload_file_client_error(mock_s3, s3_storage, email, document_id, file_obj):
    from botocore.exceptions import ClientError
    mock_s3.head_object.side_effect = ClientError({"Error": {"Code": "500"}}, "head_object")
    with pytest.raises(Exception) as exc:
        s3_storage.upload_file(email, document_id, file_obj)
    assert "S3 ClientError" in str(exc.value)
