import sys
import types
import importlib
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException


# ---------- Shared fixtures for isolation and dummy repos ----------

@pytest.fixture(autouse=True)
def _isolate_audit_service_module():
    # Ensure a fresh audit_service for each test to avoid leaked mocks/state
    sys.modules.pop('app.services.audit_service', None)
    import app.services.audit_service as audit_service  # noqa: F401
    importlib.reload(audit_service)
    yield


@pytest.fixture(autouse=True, scope="function")
def _ensure_dummy_repos_modules():
    # Provide a minimal dummy repositories namespace used by audit_service
    # Only affects tests in this directory.
    if 'app.repositories' not in sys.modules:
        sys.modules['app.repositories'] = types.ModuleType('app.repositories')
    if 'app.repositories.s3_repo' not in sys.modules:
        sys.modules['app.repositories.s3_repo'] = types.ModuleType('app.repositories.s3_repo')
        # no-op s3 writer used by audit_service (only used elsewhere)
        sys.modules['app.repositories.s3_repo'].save_json_to_s3 = lambda *a, **kw: None
    yield


# ---------- Helpers ----------

class DummyThread:
    def __init__(self, target=None, args=(), kwargs=None):
        self._target = target
        self._args = args or ()
        self._kwargs = kwargs or {}
    def start(self):
        # Run immediately to avoid background threads in tests
        if self._target:
            self._target(*self._args, **self._kwargs)


def _base_tracking_two_parties():
    # Common skeleton for tests
    return {
        "parties": [
            {"id": 1, "name": "P1", "email": "p1@example.com", "status": {}},
            {"id": 2, "name": "P2", "email": "p2@example.com", "status": {}},
        ],
        "tracking_status": {},
        "trackings": {"track123": {}}
    }


# ---------- Additional tests ----------

@pytest.mark.asyncio
@patch('app.services.audit_service.threading.Thread', side_effect=lambda target, args=(): DummyThread(target, args))
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings', return_value={"dummy": True})
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata')
@patch('app.services.audit_service.load_document_metadata')
@patch('app.services.audit_service.NotificationService')
@patch('app.services.audit_service.get_file_name', new_callable=AsyncMock, return_value='file.pdf')
async def test_all_fields_signed_activates_next_party_and_not_completed(
    mock_get_file_name,
    mock_NotificationService,
    mock_load_document,
    mock_load_tracking,
    mock_store_status,
    mock_generate_summary,
    mock_save_tracking,
    mock_thread_cls
):
    from app.services.audit_service import DocumentTrackingManager

    tracking = _base_tracking_two_parties()
    # First party previously not fully signed
    tracking["parties"][0]["status"]["signed"] = [{"isSigned": False}]
    mock_load_tracking.return_value = tracking
    mock_load_document.return_value = {"trackings": {"track123": {}}, "summary": {}}
    # NotificationService.store_notification is a static-like call in code
    mock_NotificationService.store_notification = MagicMock()

    class Data:
        ip = "1.1.1.1"; browser = "Chrome"; os = "Linux"; device = "PC"
        city = "C"; region = "R"; country = "X"; timestamp = "t"; timezone = "tz"

    await DocumentTrackingManager.log_action(
        email="user@example.com",
        document_id="doc123",
        tracking_id="track123",
        action="ALL_FIELDS_SIGNED",
        data=Data(),
        party_id=1,
        reason=None,
        name="Signer 1"
    )

    # Verify saved tracking
    assert mock_save_tracking.called
    saved_tracking = mock_save_tracking.call_args[0][3]
    # Next party should be marked as sent (dict form)
    assert "sent" in saved_tracking["parties"][1]["status"]
    assert saved_tracking["parties"][1]["status"]["sent"]["isSent"] is True
    # Not completed yet (since second party didn't sign)
    assert saved_tracking["tracking_status"]["status"] != "completed"


@pytest.mark.asyncio
@patch('app.services.audit_service.threading.Thread', side_effect=lambda target, args=(): DummyThread(target, args))
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings', return_value={"dummy": True})
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata')
@patch('app.services.audit_service.load_document_metadata')
@patch('app.services.audit_service.NotificationService')
@patch('app.services.audit_service.get_file_name', new_callable=AsyncMock, return_value='file.pdf')
async def test_all_fields_signed_marks_completed_when_all_signed(
    mock_get_file_name,
    mock_NotificationService,
    mock_load_document,
    mock_load_tracking,
    mock_store_status,
    mock_generate_summary,
    mock_save_tracking,
    mock_thread_cls
):
    from app.services.audit_service import DocumentTrackingManager

    tracking = _base_tracking_two_parties()
    # First party already signed
    tracking["parties"][0]["status"]["signed"] = [{"isSigned": True}]
    mock_load_tracking.return_value = tracking
    mock_load_document.return_value = {"trackings": {"track123": {}}, "summary": {}}
    mock_NotificationService.store_notification = MagicMock()

    class Data:
        ip = "1.1.1.1"; browser = "Chrome"; os = "Linux"; device = "PC"
        city = "C"; region = "R"; country = "X"; timestamp = "t"; timezone = "tz"

    # Now second party signs all, making tracking complete
    await DocumentTrackingManager.log_action(
        email="user@example.com",
        document_id="doc123",
        tracking_id="track123",
        action="ALL_FIELDS_SIGNED",
        data=Data(),
        party_id=2,
        reason=None,
        name="Signer 2"
    )

    assert mock_save_tracking.called
    saved_tracking = mock_save_tracking.call_args[0][3]
    assert saved_tracking["tracking_status"]["status"] == "completed"
    # Ensure second party has a signed record appended
    assert isinstance(saved_tracking["parties"][1]["status"]["signed"], list)
    assert saved_tracking["parties"][1]["status"]["signed"][-1]["isSigned"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,field,flag",
    [
        ("INITIATED", "sent", "isSent"),
        ("RE-INITIATED", "resent", "isResent"),
        ("OTP_VERIFIED", "opened", "isOpened"),
        ("fields_submitted", "resent", "isResent"),
        ("REMAINDER", "remainder", "isRemainder"),
    ]
)
@patch('app.services.audit_service.threading.Thread', side_effect=lambda target, args=(): DummyThread(target, args))
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings', return_value={"dummy": True})
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata')
@patch('app.services.audit_service.load_document_metadata')
@patch('app.services.audit_service.NotificationService')
async def test_status_updates_for_various_actions(
    mock_NotificationService,
    mock_load_document,
    mock_load_tracking,
    mock_store_status,
    mock_generate_summary,
    mock_save_tracking,
    mock_thread_cls,
    action,
    field,
    flag
):
    from app.services.audit_service import DocumentTrackingManager

    tracking = _base_tracking_two_parties()
    mock_load_tracking.return_value = tracking
    mock_load_document.return_value = {"trackings": {"track123": {}}, "summary": {}}
    mock_NotificationService.store_notification = MagicMock()

    class Data:
        ip = "1.1.1.1"; browser = "Chrome"; os = "Linux"; device = "PC"
        city = "C"; region = "R"; country = "X"; timestamp = "t"; timezone = "tz"

    await DocumentTrackingManager.log_action(
        email="user@example.com",
        document_id="doc123",
        tracking_id="track123",
        action=action,
        data=Data(),
        party_id=1,
        reason=None,
        name="Signer 1"
    )

    assert mock_save_tracking.called
    saved_tracking = mock_save_tracking.call_args[0][3]
    assert field in saved_tracking["parties"][0]["status"]
    # In non-signed flows the entry is a list
    val = saved_tracking["parties"][0]["status"][field]
    assert isinstance(val, list)
    assert val[-1][flag] is True


@pytest.mark.asyncio
@patch('app.services.audit_service.threading.Thread', side_effect=lambda target, args=(): DummyThread(target, args))
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings', return_value={"dummy": True})
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata')
@patch('app.services.audit_service.load_document_metadata')
@patch('app.services.audit_service.NotificationService')
@patch('app.services.audit_service.get_file_name', new_callable=AsyncMock, return_value='doc.pdf')
async def test_declined_requires_party_id_and_sets_party_status(
    mock_get_file_name,
    mock_NotificationService,
    mock_load_document,
    mock_load_tracking,
    mock_store_status,
    mock_generate_summary,
    mock_save_tracking,
    mock_thread_cls
):
    from app.services.audit_service import DocumentTrackingManager

    # Missing party_id should 400
    mock_load_tracking.return_value = _base_tracking_two_parties()
    mock_load_document.return_value = {"trackings": {"track123": {}}, "summary": {}}
    mock_NotificationService.store_notification = MagicMock()

    with pytest.raises(HTTPException) as exc:
        await DocumentTrackingManager.log_action(
            email="user@example.com",
            document_id="doc123",
            tracking_id="track123",
            action="DECLINED",
            data=None,
            party_id=None,
            reason="nope",
            name="N"
        )
    assert exc.value.status_code == 400

    # With party present, sets declined block
    await DocumentTrackingManager.log_action(
        email="user@example.com",
        document_id="doc123",
        tracking_id="track123",
        action="DECLINED",
        data=None,
        party_id=1,
        reason="nope",
        name="N"
    )
    saved_tracking = mock_save_tracking.call_args[0][3]
    assert saved_tracking["tracking_status"]["status"] == "declined"
    assert saved_tracking["parties"][0]["status"]["declined"]["isDeclined"] is True


@pytest.mark.asyncio
@patch('app.services.audit_service.threading.Thread', side_effect=lambda target, args=(): DummyThread(target, args))
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings', return_value={"dummy": True})
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata', side_effect=ValueError("boom"))
@patch('app.services.audit_service.load_document_metadata')
async def test_log_action_metadata_load_error_raises_404(
    mock_load_document,
    mock_load_tracking,
    mock_store_status,
    mock_generate_summary,
    mock_save_tracking,
    mock_thread_cls
):
    from app.services.audit_service import DocumentTrackingManager

    with pytest.raises(HTTPException) as exc:
        await DocumentTrackingManager.log_action(
            email="user@example.com",
            document_id="doc123",
            tracking_id="track123",
            action="INITIATED",
            data=None,
            party_id=1
        )
    assert exc.value.status_code == 404


def test_get_doc_status_no_metadata_returns_error():
    from app.services.audit_service import DocumentTrackingManager
    with patch("app.services.metadata_service.MetadataService.get_metadata", return_value=None):
        res = DocumentTrackingManager.get_doc_status("u@example.com", "t1", "d1")
        assert "error" in res and res["error"] == "Document not found"


def test_get_doc_status_cancelled_includes_cancelled_by():
    from app.services.audit_service import DocumentTrackingManager
    meta = {
        "parties": [{"id": "p1"}, {"id": "p2"}],
        "tracking_status": {"status": "cancelled"},
        "cancelled_by": {"name": "Alice", "email": "a@example.com"}
    }
    with patch("app.services.metadata_service.MetadataService.get_metadata", return_value=meta):
        res = DocumentTrackingManager.get_doc_status("u@example.com", "t1", "d1")
        assert res["tracking_status"]["status"] == "cancelled"
        assert "cancelled_by" in res and res["cancelled_by"]["name"] == "Alice"


@pytest.mark.asyncio
@patch('app.services.audit_service.threading.Thread', side_effect=lambda target, args=(): DummyThread(target, args))
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings', return_value={"dummy": True})
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata')
@patch('app.services.audit_service.load_document_metadata')
@patch('app.services.audit_service.NotificationService')
@patch('app.services.audit_service.get_file_name', new_callable=AsyncMock, return_value='cancelled.pdf')
async def test_cancel_adds_party_cancelled_and_cancelled_by(
    mock_get_file_name,
    mock_NotificationService,
    mock_load_document,
    mock_load_tracking,
    mock_store_status,
    mock_generate_summary,
    mock_save_tracking,
    mock_thread_cls
):
    from app.services.audit_service import DocumentTrackingManager

    tracking = _base_tracking_two_parties()
    mock_load_tracking.return_value = tracking
    mock_load_document.return_value = {"trackings": {"track123": {}}, "summary": {}}
    mock_NotificationService.store_notification = MagicMock()

    class Client:
        ip = "127.0.0.1"; browser = "Br"; os = "OS"; device = "Dev"
        city = "C"; region = "R"; country = "X"; timestamp = "t"; timezone = "tz"

    await DocumentTrackingManager.log_action(
        email="user@example.com",
        document_id="doc123",
        tracking_id="track123",
        action="CANCELLED",
        data=Client(),
        party_id="p1",
        reason="because",
        name="Admin",
        user_email="admin@example.com"
    )

    assert mock_save_tracking.called
    saved_tracking = mock_save_tracking.call_args[0][3]
    assert saved_tracking["tracking_status"]["status"] == "cancelled"
    assert isinstance(saved_tracking["cancelled_by"], list)
    assert saved_tracking["cancelled_by"][-1]["email"] == "admin@example.com"
    # Each party should have a cancelled list entry
    for p in saved_tracking["parties"]:
        assert "cancelled" in p["status"]
        assert p["status"]["cancelled"][-1]["isCancelled"] is True


@pytest.mark.asyncio
@patch('app.services.audit_service.threading.Thread', side_effect=lambda target, args=(): DummyThread(target, args))
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings', return_value={"dummy": True})
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata', return_value=_base_tracking_two_parties())
@patch('app.services.audit_service.load_document_metadata', return_value={"trackings": {"track123": {}}, "summary": {}})
async def test_other_action_missing_party_id_raises_400(
    mock_load_doc,
    mock_load_track,
    mock_store_status,
    mock_generate_summary,
    mock_save_tracking,
    mock_thread_cls
):
    from app.services.audit_service import DocumentTrackingManager
    with pytest.raises(HTTPException) as exc:
        await DocumentTrackingManager.log_action(
            email="user@example.com",
            document_id="doc123",
            tracking_id="track123",
            action="INITIATED",
            data=None,
            party_id=None
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
@patch('app.services.audit_service.threading.Thread', side_effect=lambda target, args=(): DummyThread(target, args))
@patch('app.services.audit_service.save_tracking_metadata')
@patch('app.services.audit_service.generate_summary_from_trackings', return_value={"dummy": True})
@patch('app.services.audit_service.store_status')
@patch('app.services.audit_service.load_tracking_metadata', return_value=_base_tracking_two_parties())
@patch('app.services.audit_service.load_document_metadata', return_value={"trackings": {"track123": {}}, "summary": {}})
async def test_other_action_party_not_found_raises_404(
    mock_load_doc,
    mock_load_track,
    mock_store_status,
    mock_generate_summary,
    mock_save_tracking,
    mock_thread_cls
):
    from app.services.audit_service import DocumentTrackingManager
    with pytest.raises(HTTPException) as exc:
        await DocumentTrackingManager.log_action(
            email="user@example.com",
            document_id="doc123",
            tracking_id="track123",
            action="INITIATED",
            data=None,
            party_id=999
        )
    assert exc.value.status_code == 404