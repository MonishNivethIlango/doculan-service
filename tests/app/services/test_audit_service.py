import sys
import types
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from app.services.audit_service import DocumentTrackingManager, document_tracking_manager

# Ensure dummy app.repositories and app.repositories.s3_repo exist for patching
if 'app.repositories' not in sys.modules:
    sys.modules['app.repositories'] = types.ModuleType('app.repositories')
if 'app.repositories.s3_repo' not in sys.modules:
    sys.modules['app.repositories.s3_repo'] = types.ModuleType('app.repositories.s3_repo')
    sys.modules['app.repositories.s3_repo'].save_json_to_s3 = lambda *a, **kw: None

def test_get_party_doc_sts():
    metadata = {"fields": [{"partyId": 1, "field": "f1"}, {"partyId": 2, "field": "f2"}], "tracking_status": {"status": "sent"}}
    party = {"id": 1, "name": "A"}
    result = DocumentTrackingManager.get_party_doc_sts("doc1", metadata, party, 1, "track1")
    assert result["tracking_id"] == "track1"
    assert result["document_id"] == "doc1"
    assert result["party_id"] == 1
    assert result["fields"] == [{"partyId": 1, "field": "f1"}]
    assert result["tracking_status"] == {"status": "sent"}

@pytest.mark.asyncio
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings')
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata')
@patch('app.services.audit_service.load_document_metadata')
@patch('app.services.audit_service.NotificationService')
@patch('app.services.audit_service.get_file_name', new_callable=AsyncMock, return_value='file.pdf')
async def test_log_action_declined_party_not_found(
    mock_get_file_name, mock_NotificationService, mock_load_doc, mock_load_track, mock_store_status, mock_generate_summary, mock_save_track
):
    # No party with id=1, so should raise HTTPException
    mock_load_track.return_value = {"parties": [{"id": 2, "status": {}}], "tracking_status": {}}
    mock_load_doc.return_value = {"trackings": {"track": {}}, "summary": {}}
    mock_NotificationService.return_value.store_notification = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await DocumentTrackingManager.log_action("email", "doc", "track", "DECLINED", MagicMock(), party_id=1, reason="r", name="n")
    assert exc.value.status_code == 404

@pytest.mark.asyncio
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings')
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata')
@patch('app.services.audit_service.load_document_metadata')
@patch('app.services.audit_service.NotificationService')
@patch('app.services.audit_service.get_file_name', new_callable=AsyncMock, return_value='file.pdf')
async def test_log_action_declined_party_found(
    mock_get_file_name, mock_NotificationService, mock_load_doc, mock_load_track, mock_store_status, mock_generate_summary, mock_save_track
):
    # Use string id to match possible implementation
    mock_load_track.return_value = {"parties": [{"id": "1", "status": {}}], "tracking_status": {}}
    mock_load_doc.return_value = {"trackings": {"track": {}}, "summary": {}}
    mock_NotificationService.return_value.store_notification = AsyncMock()
    class Data:
        ip = "1.1.1.1"
        browser = "Chrome"
        os = "Linux"
        device = "PC"
        city = "C"
        region = "R"
        country = "X"
        timestamp = "t"
        timezone = "tz"
    await DocumentTrackingManager.log_action("email", "doc", "track", "DECLINED", Data(), party_id="1", reason="r", name="n")
    assert mock_save_track.called
    assert mock_store_status.called
    # Notification is not expected for DECLINED in most implementations

@pytest.mark.asyncio
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings')
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata')
@patch('app.services.audit_service.load_document_metadata')
@patch('app.services.audit_service.NotificationService')
@patch('app.services.audit_service.get_file_name', new_callable=AsyncMock, return_value='file.pdf')
async def test_log_action_initiated_all_fields_signed(
    mock_get_file_name, mock_NotificationService, mock_load_doc, mock_load_track, mock_store_status, mock_generate_summary, mock_save_track
):
    mock_load_track.return_value = {"parties": [{"id": 1, "status": {"signed": [{"isSigned": True}]}}], "tracking_status": {}}
    mock_load_doc.return_value = {"trackings": {"track": {}}, "summary": {}}
    mock_NotificationService.return_value.store_notification = AsyncMock()
    class Data:
        ip = "1.1.1.1"
        browser = "Chrome"
        os = "Linux"
        device = "PC"
        city = "C"
        region = "R"
        country = "X"
        timestamp = "t"
        timezone = "tz"
    await DocumentTrackingManager.log_action("email", "doc", "track", "ALL_FIELDS_SIGNED", Data(), party_id=1, reason="r", name="n")
    assert mock_save_track.called
    assert mock_store_status.called

@pytest.mark.asyncio
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings')
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata')
@patch('app.services.audit_service.load_document_metadata')
@patch('app.services.audit_service.NotificationService')
@patch('app.services.audit_service.get_file_name', new_callable=AsyncMock, return_value='file.pdf')
async def test_log_action_initiated_not_all_signed(
    mock_get_file_name, mock_NotificationService, mock_load_doc, mock_load_track, mock_store_status, mock_generate_summary, mock_save_track
):
    mock_load_track.return_value = {"parties": [{"id": 1, "status": {"signed": [{"isSigned": False}]}}, {"id": 2, "status": {}}], "tracking_status": {}}
    mock_load_doc.return_value = {"trackings": {"track": {}}, "summary": {}}
    mock_NotificationService.return_value.store_notification = AsyncMock()
    class Data:
        ip = "1.1.1.1"
        browser = "Chrome"
        os = "Linux"
        device = "PC"
        city = "C"
        region = "R"
        country = "X"
        timestamp = "t"
        timezone = "tz"
    await DocumentTrackingManager.log_action("email", "doc", "track", "ALL_FIELDS_SIGNED", Data(), party_id=1, reason="r", name="n")
    assert mock_save_track.called
    assert mock_store_status.called

@pytest.fixture
def mock_metadata():
    return {
        "fields": [{"id": "f1", "partyId": "p1"}],
        "parties": [{"id": "p1", "name": "Party 1", "email": "p1@example.com", "status": {}}],
        "tracking_status": {"status": "in_progress"}
    }

@pytest.fixture
def mock_party():
    return {"id": "p1", "name": "Party 1", "email": "p1@example.com"}

@patch("app.services.metadata_service.MetadataService.get_metadata")
def test_get_doc_status_success(mock_get_metadata, mock_metadata):
    mock_get_metadata.return_value = mock_metadata
    result = DocumentTrackingManager.get_doc_status("user@example.com", "tracking123", "doc123")
    assert result["document_id"] == "doc123"
    assert result["tracking_id"] == "tracking123"
    assert result["tracking_status"] == {"status": "in_progress"}

@patch("app.services.audit_service.get_all_document_statuses_flat")
def test_get_all_doc_sts(mock_get_statuses):
    expected_data = [
        {"document_id": "doc1", "status": "completed"},
        {"document_id": "doc2", "status": "in_progress"},
    ]
    mock_get_statuses.return_value = expected_data
    result = DocumentTrackingManager.get_all_doc_sts(email="user@example.com")
    assert result == expected_data
    mock_get_statuses.assert_called_once_with("user@example.com")

def test_validate_party_and_initialize_status_success(mock_metadata):
    class Dummy:
        party_id = "p1"
    fields, party_status = DocumentTrackingManager.validate_party_and_initialize_status(Dummy(), mock_metadata, signed_any=True)
    assert len(fields) == 1
    assert "status" in party_status

def test_validate_party_and_initialize_status_missing_party():
    mock_meta = {"fields": [], "parties": []}
    class Dummy:
        party_id = "x"
    with pytest.raises(HTTPException) as exc:
        DocumentTrackingManager.validate_party_and_initialize_status(Dummy(), mock_meta, signed_any=True)
    assert exc.value.status_code == 400 or exc.value.status_code == 404

def test_initialize_parties_status_success():
    class Dummy:
        document_id = "doc001"
        parties = [
            type("Party", (), {"id": "p1", "name": "Party 1", "email": "p1@example.com", "color": "red"})(),
            type("Party", (), {"id": "p2", "name": "Party 2", "email": "p2@example.com", "color": "blue"})(),
        ]
    parties_status = document_tracking_manager.initialize_parties_status(Dummy())
    assert len(parties_status) == 2
    assert all("status" in p for p in parties_status)

def test_initialize_parties_status_failure():
    class Dummy:
        pass
    with pytest.raises(HTTPException):
        DocumentTrackingManager.initialize_parties_status(Dummy())

@pytest.mark.asyncio
@patch("app.services.audit_service.save_tracking_metadata")
@patch("app.services.audit_service.load_document_metadata")
@patch("app.services.audit_service.load_tracking_metadata")
@patch("app.services.audit_service.NotificationService")
async def test_log_action_cancel(
    mock_NotificationService, mock_load_tracking, mock_load_document, mock_save_tracking
):
    mock_save_tracking.return_value = None
    mock_load_tracking.return_value = {
        "parties": [{"id": "p1", "status": {}}],
        "tracking_status": {"status": "in_progress"}
    }
    mock_load_document.return_value = {"trackings": {"track123": {}}, "summary": {}}
    mock_NotificationService.return_value.store_notification = AsyncMock()

    manager = DocumentTrackingManager()
    await manager.log_action(
        email="user@example.com",
        document_id="doc123",
        tracking_id="track123",
        action="CANCELLED",
        data=None,
        party_id="p1",
        reason="Test reason",
        name="Test User"
    )

    assert mock_save_tracking.called

    class DummyClient:
        ip = "127.0.0.1"
        browser = "Chrome"
        os = "Windows"
        device = "PC"
        city = "TestCity"
        region = "TestRegion"
        country = "TestCountry"
        timestamp = "2025-08-13T00:00:00Z"
        timezone = "UTC"

    class DummyHolder:
        name = "Test User"
        email = "holder@example.com"

    class DummyData:
        document_id = "doc123"
        tracking_id = "track123"
        action = "CANCELLED"
        holder = DummyHolder()
        party_id = "p1"
        reason = "Test reason"

    # Call as staticmethod
    result = await DocumentTrackingManager.log_action_cancel(
        DummyData(), DummyClient(), "user@example.com", "holder@example.com"
    )
    assert isinstance(result, dict)
    assert "message" in result