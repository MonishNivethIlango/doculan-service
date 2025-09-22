import sys
from unittest.mock import MagicMock

# Patch DB and S3 before importing app code
sys.modules['auth_app.app.database.connection'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['database.db_config'] = MagicMock()
sys.modules['repositories.s3_repo'] = MagicMock()
sys.modules['utils.logger'] = MagicMock()
sys.modules['auth_app.app.model.UserModel'] = MagicMock()

import pytest
from unittest.mock import patch, MagicMock
from app.services.tracking_service import TrackingService

@pytest.fixture
def service():
    return TrackingService(email="user@example.com")

# --- get_tracking_by_id ---

@patch("app.services.tracking_service.load_tracking_metadata")
def test_get_tracking_by_id_success(mock_load, service):
    mock_load.return_value = {"tracking_id": "tid"}
    result = service.get_tracking_by_id("doc1", "tid")
    assert result == {"tracking_id": "tid"}
    mock_load.assert_called_once_with("user@example.com", "doc1", "tid")

@patch("app.services.tracking_service.load_tracking_metadata", side_effect=Exception("fail"))
def test_get_tracking_by_id_exception(mock_load, service):
    with pytest.raises(Exception):
        service.get_tracking_by_id("doc1", "tid")

# --- get_tracking_fields ---

@patch.object(TrackingService, "get_tracking_by_id")
def test_get_tracking_fields_all_fields(mock_get, service):
    mock_get.return_value = {
        "email_response": [{"a": 1}],
        "parties": [{"b": 2}],
        "remainder": 3,
        "validityDate": "2025-09-19"
    }
    result = service.get_tracking_fields("doc1", "tid")
    assert result[0] == [{"a": 1}]
    assert result[1] == [{"b": 2}]
    assert result[2] == 3
    assert result[3]["email_response"] == [{"a": 1}]
    assert result[4] == "2025-09-19"

@patch.object(TrackingService, "get_tracking_by_id")
def test_get_tracking_fields_missing_fields(mock_get, service):
    mock_get.return_value = {}
    result = service.get_tracking_fields("doc1", "tid")
    assert result[0] == []
    assert result[1] == []
    assert result[2] == 1
    assert result[3] == {}
    assert result[4] == ""

# --- get_all_tracking_ids_status ---

@patch("app.services.tracking_service.get_role_document_ids")
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_admin_no_files(mock_config, mock_s3, mock_get_role, service):
    mock_config.S3_BUCKET = "bucket"
    mock_s3.list_objects_v2.return_value = {"Contents": []}
    result = service.get_all_tracking_ids_status("admin")
    assert result["total_trackings"] == 0
    assert result["documents"] == {}

@patch("app.services.tracking_service.get_role_document_ids")
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_nonadmin_no_docs(mock_config, mock_s3, mock_get_role, service):
    mock_config.S3_BUCKET = "bucket"
    mock_get_role.return_value = {"documentIds": []}
    result = service.get_all_tracking_ids_status("user")
    assert result["total_trackings"] == 0
    assert result["documents"] == {}

@patch("app.services.tracking_service.get_role_document_ids")
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_files_found(mock_config, mock_s3, mock_get_role, service):
    mock_config.S3_BUCKET = "bucket"
    mock_get_role.return_value = {"documentIds": ["doc1"]}
    # Simulate two files
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "user@example.com/trackings/doc1/t1.json"},
            {"Key": "user@example.com/trackings/doc1/t2.json"}
        ]
    }
    # Patch s3_client.get_object and file content
    def get_object_side_effect(Bucket, Key):
        class Body:
            def read(self):
                if "t1" in Key:
                    return b'{"document_id": "doc1", "tracking_id": "t1", "tracking_status": {"status": "completed", "dateTime": "now"}, "parties": []}'
                else:
                    return b'{"document_id": "doc1", "tracking_id": "t2", "tracking_status": {"status": "in_progress", "dateTime": "now"}, "parties": []}'
        return {"Body": Body()}
    mock_s3.get_object.side_effect = get_object_side_effect

    result = service.get_all_tracking_ids_status("user")
    assert result["total_trackings"] == 2
    assert "doc1" in result["documents"]
    assert "completed" in result["documents"]["doc1"]
    assert "in_progress" in result["documents"]["doc1"]

@patch("app.services.tracking_service.get_role_document_ids")
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_unknown_status(mock_config, mock_s3, mock_get_role, service):
    mock_config.S3_BUCKET = "bucket"
    mock_get_role.return_value = {"documentIds": ["doc1"]}
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "user@example.com/trackings/doc1/t1.json"}
        ]
    }
    def get_object_side_effect(Bucket, Key):
        class Body:
            def read(self):
                return b'{"document_id": "doc1", "tracking_id": "t1", "tracking_status": {"status": "mystery"}, "parties": []}'
        return {"Body": Body()}
    mock_s3.get_object.side_effect = get_object_side_effect

    result = service.get_all_tracking_ids_status("user")
    assert result["status_counts"]["unknown"] == 1

@patch("app.services.tracking_service.get_role_document_ids")
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_processing_error(mock_config, mock_s3, mock_get_role, service):
    mock_config.S3_BUCKET = "bucket"
    mock_get_role.return_value = {"documentIds": ["doc1"]}
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "user@example.com/trackings/doc1/t1.json"}
        ]
    }
    # Simulate error in get_object
    mock_s3.get_object.side_effect = Exception("fail")
    result = service.get_all_tracking_ids_status("user")
    assert result["total_trackings"] == 0
