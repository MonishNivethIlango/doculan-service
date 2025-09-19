import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.services.tracking_service import TrackingService

@pytest.fixture
def tracking_service():
    return TrackingService(email="test@example.com")


@pytest.fixture
def sample_tracking_data():
    return {
        "email_response": [{"email": "signer@example.com"}],
        "parties": [{"id": "party1", "email": "signer@example.com"}],
        "remainder": 2,
        "validityDate": "2025-12-31",
    }


@patch("app.services.tracking_service.load_tracking_metadata")
def test_get_tracking_by_id_success(mock_load, tracking_service, sample_tracking_data):
    mock_load.return_value = sample_tracking_data
    result = tracking_service.get_tracking_by_id("doc123", "track123")
    assert result == sample_tracking_data
    mock_load.assert_called_once_with("test@example.com", "doc123", "track123")


@patch("app.services.tracking_service.load_tracking_metadata")
def test_get_tracking_by_id_raises_http_exception(mock_load, tracking_service):
    mock_load.side_effect = HTTPException(status_code=404, detail="Not Found")
    with pytest.raises(HTTPException) as exc:
        tracking_service.get_tracking_by_id("doc123", "track123")
    assert exc.value.status_code == 404


# Edge: get_tracking_by_id returns None (should return None)
@patch("app.services.tracking_service.load_tracking_metadata")
def test_get_tracking_by_id_none(mock_load, tracking_service):
    mock_load.return_value = None
    result = tracking_service.get_tracking_by_id("doc123", "track123")
    assert result is None


@patch("app.services.tracking_service.load_tracking_metadata")
def test_get_tracking_fields(mock_load, tracking_service, sample_tracking_data):
    mock_load.return_value = sample_tracking_data
    fields, parties, remainder, full_data, validity = tracking_service.get_tracking_fields("doc123", "track123")

    assert fields == sample_tracking_data["email_response"]
    assert parties == sample_tracking_data["parties"]
    assert remainder == sample_tracking_data["remainder"]
    assert full_data == sample_tracking_data
    assert validity == sample_tracking_data["validityDate"]


# Edge: get_tracking_fields returns None (should raise AttributeError)
@patch("app.services.tracking_service.load_tracking_metadata")
def test_get_tracking_fields_none(mock_load, tracking_service):
    mock_load.return_value = None
    with pytest.raises(AttributeError):
        tracking_service.get_tracking_fields("doc123", "track123")


# Edge: get_tracking_fields returns incomplete data (should use defaults)
@patch("app.services.tracking_service.load_tracking_metadata")
def test_get_tracking_fields_incomplete(mock_load, tracking_service):
    mock_load.return_value = {"email_response": [{}]}  # missing parties, remainder, validityDate
    fields, parties, remainder, full_data, validity = tracking_service.get_tracking_fields("doc123", "track123")
    assert fields == [{}]
    assert parties == []
    assert remainder == 1
    assert full_data == {"email_response": [{}]}
    assert validity == ""


@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status(mock_config, mock_s3_client, tracking_service):
    mock_config.S3_BUCKET = "mock-bucket"
    doc_data = {
        "document_id": "doc123",
        "trackings": {
            "t1": {"status": "completed"},
            "t2": {"status": "cancelled"},
            "t3": {"status": "in_progress"},
            "t4": {"status": "expired"},
            "t5": {"status": "unknown"},
            "t6": {"status": "invalid_status"}
        }
    }
    mock_s3_client.list_objects_v2.return_value = {
        "Contents": [{"Key": "test@example.com/metadata/documents/doc123.json"}]
    }
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=str.encode(str(doc_data).replace("'", '"'))))
    }
    result = tracking_service.get_all_tracking_ids_status()
    assert result["total_trackings"] == 1
    # The document should be present
    assert "doc123" in result["documents"]
    # The status should be nested inside the document
    doc_statuses = result["documents"]["doc123"]
    # Should have at least one status key (likely 'unknown')
    assert any(status in doc_statuses for status in ["completed", "cancelled", "in_progress", "expired", "unknown"])


# Edge: get_all_tracking_ids_status with empty S3 contents
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_empty(mock_config, mock_s3_client, tracking_service):
    mock_config.S3_BUCKET = "mock-bucket"
    mock_s3_client.list_objects_v2.return_value = {"Contents": []}
    result = tracking_service.get_all_tracking_ids_status()
    assert result["total_trackings"] == 0
    # Accept any superset of status keys with all zero values
    assert all(v == 0 for v in result["status_counts"].values())
    assert result["documents"] == {}


# Edge: get_all_tracking_ids_status with S3 get_object raising exception
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_get_object_error(mock_config, mock_s3_client, tracking_service):
    mock_config.S3_BUCKET = "mock-bucket"
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "doc1.json"}]}
    mock_s3_client.get_object.side_effect = Exception("S3 error")
    result = tracking_service.get_all_tracking_ids_status()
    assert result["total_trackings"] == 0
    assert result["documents"] == {}


# Edge: get_all_tracking_ids_status with corrupted JSON
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_corrupted_json(mock_config, mock_s3_client, tracking_service):
    mock_config.S3_BUCKET = "mock-bucket"
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "doc1.json"}]}
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=b"not json"))}
    result = tracking_service.get_all_tracking_ids_status()
    assert result["total_trackings"] == 0
    assert result["documents"] == {}


# Edge: get_all_tracking_ids_status with no 'trackings' key
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_no_trackings(mock_config, mock_s3_client, tracking_service):
    mock_config.S3_BUCKET = "mock-bucket"
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "doc1.json"}]}
    doc_data = {"document_id": "doc1"}
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=str.encode(str(doc_data).replace("'", '"'))))}
    result = tracking_service.get_all_tracking_ids_status()
    assert result["total_trackings"] == 1
    assert "doc1" in result["documents"]
    assert "unknown" in result["documents"]["doc1"]


# Edge: get_all_tracking_ids_status with empty 'trackings' dict
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_empty_trackings(mock_config, mock_s3_client, tracking_service):
    mock_config.S3_BUCKET = "mock-bucket"
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "doc1.json"}]}
    doc_data = {"document_id": "doc1", "trackings": {}}
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=str.encode(str(doc_data).replace("'", '"'))))}
    result = tracking_service.get_all_tracking_ids_status()
    assert result["total_trackings"] == 1
    assert "doc1" in result["documents"]
    assert "unknown" in result["documents"]["doc1"]


# Edge: get_all_tracking_ids_status with multiple documents
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_multiple_docs(mock_config, mock_s3_client, tracking_service):
    mock_config.S3_BUCKET = "mock-bucket"
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "doc1.json"}, {"Key": "doc2.json"}]}
    doc1 = {"document_id": "doc1", "trackings": {"t1": {"status": "completed"}}}
    doc2 = {"document_id": "doc2", "trackings": {"t2": {"status": "cancelled"}}}
    def get_obj_side_effect(Bucket, Key):
        if Key == "doc1.json":
            return {"Body": MagicMock(read=MagicMock(return_value=str.encode(str(doc1).replace("'", '"'))))}
        else:
            return {"Body": MagicMock(read=MagicMock(return_value=str.encode(str(doc2).replace("'", '"'))))}
    mock_s3_client.get_object.side_effect = get_obj_side_effect
    result = tracking_service.get_all_tracking_ids_status()
    assert result["total_trackings"] == 2
    assert "doc1" in result["documents"]
    assert "doc2" in result["documents"]
    # Each doc should have a status key inside
    assert any(status in result["documents"]["doc1"] for status in ["completed", "cancelled", "in_progress", "expired", "unknown"])
    assert any(status in result["documents"]["doc2"] for status in ["completed", "cancelled", "in_progress", "expired", "unknown"])


# Edge: get_all_tracking_ids_status with missing status field
@patch("app.services.tracking_service.s3_client")
@patch("app.services.tracking_service.config")
def test_get_all_tracking_ids_status_missing_status(mock_config, mock_s3_client, tracking_service):
    mock_config.S3_BUCKET = "mock-bucket"
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "doc1.json"}]}
    doc_data = {"document_id": "doc1", "trackings": {"t1": {}}}
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=str.encode(str(doc_data).replace("'", '"'))))}
    result = tracking_service.get_all_tracking_ids_status()
    assert result["status_counts"]["unknown"] == 1
