import sys
from unittest.mock import MagicMock

# Patch DB connection before importing app code
sys.modules['auth_app.app.database.connection'] = MagicMock(
    db=MagicMock(),
    save_document_url=MagicMock(),
    tracker_collection=MagicMock()
)

import pytest
from unittest.mock import patch, MagicMock
from app.services.notification_service import NotificationService

# --- store_notification ---

@patch("app.services.notification_service.s3_upload_json")
@patch("app.services.notification_service.logger")
def test_store_notification_completed(mock_logger, mock_s3):
    NotificationService.store_notification(
        email="user@example.com",
        user_email="owner@example.com",
        document_id="doc1",
        tracking_id="track1",
        document_name="Doc",
        parties_status=[{"id": "1", "name": "Alice", "email": "alice@example.com", "status": "completed"}],
        timestamp="2025-09-19T12:00:00Z"
    )
    mock_s3.assert_called_once()
    mock_logger.info.assert_called()

@patch("app.services.notification_service.s3_upload_json")
@patch("app.services.notification_service.logger")
def test_store_notification_cancelled(mock_logger, mock_s3):
    NotificationService.store_notification(
        email="user@example.com",
        user_email="owner@example.com",
        document_id="doc1",
        tracking_id="track1",
        document_name="Doc",
        parties_status=[],
        timestamp="2025-09-19T12:00:00Z",
        action="cancelled",
        party_name="Bob"
    )
    mock_s3.assert_called_once()
    mock_logger.info.assert_called()

@patch("app.services.notification_service.s3_upload_json")
@patch("app.services.notification_service.logger")
def test_store_notification_declined_with_reason(mock_logger, mock_s3):
    NotificationService.store_notification(
        email="user@example.com",
        user_email="owner@example.com",
        document_id="doc1",
        tracking_id="track1",
        document_name="Doc",
        parties_status=[],
        timestamp="2025-09-19T12:00:00Z",
        action="declined",
        party_name="Bob",
        reason="Not interested"
    )
    mock_s3.assert_called_once()
    mock_logger.info.assert_called()

@patch("app.services.notification_service.s3_upload_json")
@patch("app.services.notification_service.logger")
def test_store_notification_dispatched_with_reason(mock_logger, mock_s3):
    NotificationService.store_notification(
        email="user@example.com",
        user_email="owner@example.com",
        document_id="doc1",
        tracking_id="track1",
        document_name="Doc",
        parties_status=[],
        timestamp="2025-09-19T12:00:00Z",
        action="dispatched",
        party_name="Bob",
        reason="Urgent"
    )
    mock_s3.assert_called_once()
    mock_logger.info.assert_called()

@patch("app.services.notification_service.s3_upload_json")
@patch("app.services.notification_service.logger")
def test_store_notification_failed_with_reason(mock_logger, mock_s3):
    NotificationService.store_notification(
        email="user@example.com",
        user_email="owner@example.com",
        document_id="doc1",
        tracking_id="track1",
        document_name="Doc",
        parties_status=[],
        timestamp="2025-09-19T12:00:00Z",
        action="failed",
        party_name="Bob",
        reason="Network error"
    )
    mock_s3.assert_called_once()
    mock_logger.info.assert_called()

@patch("app.services.notification_service.s3_upload_json", side_effect=Exception("S3 error"))
@patch("app.services.notification_service.logger")
def test_store_notification_exception(mock_logger, mock_s3):
    NotificationService.store_notification(
        email="user@example.com",
        user_email="owner@example.com",
        document_id="doc1",
        tracking_id="track1",
        document_name="Doc",
        parties_status=[],
        timestamp="2025-09-19T12:00:00Z"
    )
    mock_logger.exception.assert_called()

# --- store_form_notification (if async) ---

import asyncio

@patch("app.services.notification_service.s3_upload_json")
@patch("app.services.notification_service.logger")
@pytest.mark.asyncio
async def test_store_form_notification_success(mock_logger, mock_s3):
    await NotificationService.store_form_notification(
        email="user@example.com",
        user_email="owner@example.com",
        form_id="form1",
        form_title="Form Title",
        party_email="party@example.com",
        timestamp="2025-09-19T12:00:00Z",
        party_name="Alice"
    )
    mock_s3.assert_called_once()
    mock_logger.info.assert_called()

@patch("app.services.notification_service.s3_upload_json", side_effect=Exception("S3 error"))
@patch("app.services.notification_service.logger")
@pytest.mark.asyncio
async def test_store_form_notification_exception(mock_logger, mock_s3):
    await NotificationService.store_form_notification(
        email="user@example.com",
        user_email="owner@example.com",
        form_id="form1",
        form_title="Form Title",
        party_email="party@example.com",
        timestamp="2025-09-19T12:00:00Z",
        party_name="Alice"
    )
    mock_logger.exception.assert_called()