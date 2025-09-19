import pytest
from unittest.mock import patch, MagicMock
from app.services.notification_service import NotificationService

@pytest.fixture
def sample_parties_status():
    return [
        {"id": "p1", "name": "Party One", "email": "p1@example.com", "status": "pending"},
        {"id": "p2", "name": "Party Two", "email": "p2@example.com", "status": "signed"}
    ]

def test_store_notification_completed(sample_parties_status):
    with patch("app.services.notification_service.s3_upload_json") as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name="DocName",
            parties_status=sample_parties_status,
            timestamp="2025-08-13T12:00:00Z"
        )
        assert mock_upload.called
        assert mock_logger.info.called
        args, kwargs = mock_upload.call_args
        notification, s3_key = args
        assert notification["status"] == "completed"
        assert "All parties have signed" in notification["message"]
        assert notification["read"] is False
        assert notification["parties"][0]["id"] == "p1"
        assert s3_key.startswith("user@example.com/notifications/notif-")

def test_store_notification_cancelled(sample_parties_status):
    with patch("app.services.notification_service.s3_upload_json") as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name="DocName",
            parties_status=sample_parties_status,
            timestamp="2025-08-13T12:00:00Z",
            action="cancelled",
            party_name="Party One"
        )
        notification = mock_upload.call_args[0][0]
        assert notification["status"] == "cancelled"
        assert "was cancelled by Party One" in notification["message"]

def test_store_notification_declined_with_reason(sample_parties_status):
    with patch("app.services.notification_service.s3_upload_json") as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name="DocName",
            parties_status=sample_parties_status,
            timestamp="2025-08-13T12:00:00Z",
            action="declined",
            party_name="Party Two",
            reason="Signature mismatch"
        )
        notification = mock_upload.call_args[0][0]
        assert notification["status"] == "declined"
        assert "was declined by Party Two" in notification["message"]
        assert "Reason: Signature mismatch" in notification["message"]

def test_store_notification_declined_no_reason(sample_parties_status):
    with patch("app.services.notification_service.s3_upload_json") as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name="DocName",
            parties_status=sample_parties_status,
            timestamp="2025-08-13T12:00:00Z",
            action="declined",
            party_name="Party Two"
        )
        notification = mock_upload.call_args[0][0]
        assert notification["status"] == "declined"
        assert "was declined by Party Two" in notification["message"]
        assert "Reason:" not in notification["message"]

def test_store_notification_missing_party_fields():
    # parties_status is empty, party_name and party_email are None
    with patch("app.services.notification_service.s3_upload_json") as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name="DocName",
            parties_status=[],
            timestamp="2025-08-13T12:00:00Z"
        )
        notification = mock_upload.call_args[0][0]
        assert notification["party_name"] == "-"
        assert notification["party_email"] == "-"
        assert notification["parties"] == []

def test_store_notification_upload_exception(sample_parties_status):
    with patch("app.services.notification_service.s3_upload_json", side_effect=Exception("fail")) as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name="DocName",
            parties_status=sample_parties_status,
            timestamp="2025-08-13T12:00:00Z"
        )
        assert mock_logger.exception.called

def test_store_notification_missing_document_name(sample_parties_status):
    with patch("app.services.notification_service.s3_upload_json") as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name=None,
            parties_status=sample_parties_status,
            timestamp="2025-08-13T12:00:00Z"
        )
        notification = mock_upload.call_args[0][0]
        assert "document 'None'" in notification["message"]

def test_store_notification_missing_parties_status():
    with patch("app.services.notification_service.s3_upload_json") as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name="DocName",
            parties_status=None,
            timestamp="2025-08-13T12:00:00Z"
        )
        mock_upload.assert_not_called()
        assert mock_logger.exception.called

def test_store_notification_invalid_parties_status_type():
    with patch("app.services.notification_service.s3_upload_json") as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name="DocName",
            parties_status="notalist",
            timestamp="2025-08-13T12:00:00Z"
        )
        mock_upload.assert_not_called()
        assert mock_logger.exception.called

def test_store_notification_s3_upload_json_unexpected_error(sample_parties_status):
    with patch("app.services.notification_service.s3_upload_json", side_effect=RuntimeError("unexpected error")) as mock_upload, \
         patch("app.services.notification_service.logger") as mock_logger:
        NotificationService.store_notification(
            email="user@example.com",
            document_id="doc1",
            tracking_id="track1",
            document_name="DocName",
            parties_status=sample_parties_status,
            timestamp="2025-08-13T12:00:00Z"
        )
        assert mock_logger.exception.called
