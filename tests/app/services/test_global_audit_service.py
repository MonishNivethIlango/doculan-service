import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from app.services.global_audit_service import GlobalAuditService

@pytest.fixture
def sample_actor():
    return {"id": "user1", "role": "admin"}

@pytest.fixture
def sample_metadata():
    return {"ip": "127.0.0.1"}

@pytest.fixture
def sample_targets():
    return [{"id": "target1"}]

def test_get_doc_audit_key():
    assert GlobalAuditService._get_doc_audit_key("test@example.com") == "test@example.com/audit/all_logs_document.json"

def test_get_form_audit_key():
    assert GlobalAuditService._get_form_audit_key("test@example.com") == "test@example.com/audit/all_logs_form.json"

def test_append_log_success():
    with patch("app.services.global_audit_service.append_logs") as mock_append:
        GlobalAuditService._append_log("key", {"entry": 1})
        mock_append.assert_called_once_with({"entry": 1}, "key")
def test_append_log_failure():
    with patch("app.services.global_audit_service.append_logs", side_effect=Exception("fail")):
        with pytest.raises(HTTPException) as exc:
            GlobalAuditService._append_log("key", {"entry": 1})
        assert exc.value.status_code == 500
        assert "Failed to write audit log" in str(exc.value.detail)
def test_create_entry(sample_actor, sample_metadata, sample_targets):
    entry = GlobalAuditService._create_entry(
        "entity", "eid", "action", sample_actor, sample_metadata, sample_targets
    )
    assert entry["entity"] == "entity"
    assert entry["entity_id"] == "eid"
    assert entry["action"] == "action"
    assert entry["actor"] == sample_actor
    assert entry["metadata"] == sample_metadata
    assert entry["targets"] == sample_targets
    assert "timestamp" in entry

def test_log_document_action_calls_all(sample_actor):
    with patch.object(GlobalAuditService, "_get_doc_audit_key", return_value="key") as mkey, \
         patch.object(GlobalAuditService, "_create_entry", return_value={"entry": 1}) as mentry, \
         patch.object(GlobalAuditService, "_append_log") as mappend:
        GlobalAuditService.log_document_action("email", "docid", "act", sample_actor)
        mkey.assert_called_once_with("email")
        mentry.assert_called_once()
        mappend.assert_called_once_with("key", {"entry": 1})

def test_log_document_action_append_log_fail(sample_actor):
    with patch.object(GlobalAuditService, "_get_doc_audit_key", return_value="key"), \
         patch.object(GlobalAuditService, "_create_entry", return_value={}), \
         patch.object(GlobalAuditService, "_append_log", side_effect=HTTPException(status_code=500, detail="fail")):
        with pytest.raises(HTTPException):
            GlobalAuditService.log_document_action("email", "docid", "act", sample_actor)

def test_log_form_action_calls_all(sample_actor):
    with patch.object(GlobalAuditService, "_get_form_audit_key", return_value="key") as mkey, \
         patch.object(GlobalAuditService, "_create_entry", return_value={"entry": 1}) as mentry, \
         patch.object(GlobalAuditService, "_append_log") as mappend:
        GlobalAuditService.log_form_action("email", "fid", "act", sample_actor)
        mkey.assert_called_once_with("email")
        mentry.assert_called_once()
        mappend.assert_called_once_with("key", {"entry": 1})

def test_log_form_action_append_log_fail(sample_actor):
    with patch.object(GlobalAuditService, "_get_form_audit_key", return_value="key"), \
         patch.object(GlobalAuditService, "_create_entry", return_value={}), \
         patch.object(GlobalAuditService, "_append_log", side_effect=HTTPException(status_code=500, detail="fail")):
        with pytest.raises(HTTPException):
            GlobalAuditService.log_form_action("email", "fid", "act", sample_actor)

def test_get_document_logs_success():
    with patch("app.services.global_audit_service.get_logs", return_value=[{"entity_id": "docid"}]) as mget, \
         patch("app.services.global_audit_service.s3_client") as ms3:
        ms3.exceptions.NoSuchKey = Exception
    logs = GlobalAuditService.get_document_logs("email")
    assert logs == [{"entity_id": "docid"}]
    mget.assert_called_once()
def test_get_document_logs_no_such_key():
    class DummyEx(Exception):
        pass
    with patch("app.services.global_audit_service.get_logs", side_effect=DummyEx), \
         patch("app.services.global_audit_service.s3_client") as ms3:
        ms3.exceptions.NoSuchKey = DummyEx
        logs = GlobalAuditService.get_document_logs("email")
        assert logs == []

def test_get_document_logs_other_exception():
    class NotNoSuchKey(Exception):
        pass
    with patch("app.services.global_audit_service.get_logs", side_effect=NotNoSuchKey("fail")), \
         patch("app.services.global_audit_service.s3_client") as ms3:
        class DummyEx(Exception):
            pass
        ms3.exceptions.NoSuchKey = DummyEx
        with pytest.raises(HTTPException) as exc:
            GlobalAuditService.get_document_logs("email")
        assert exc.value.status_code == 500
        assert "Failed to fetch document audit logs" in str(exc.value.detail)

def test_get_form_logs_success():
    class DummyEx(Exception):
        pass
    with patch("app.services.global_audit_service.get_logs", return_value=[{"entity_id": "fid"}]) as mget, \
         patch("app.services.global_audit_service.s3_client") as ms3:
        ms3.exceptions.NoSuchKey = DummyEx
        logs = GlobalAuditService.get_form_logs("email")
        assert logs == [{"entity_id": "fid"}]
        mget.assert_called_once()
def test_get_form_logs_no_such_key():
    class DummyEx(Exception):
        pass
    with patch("app.services.global_audit_service.get_logs", side_effect=DummyEx), \
         patch("app.services.global_audit_service.s3_client") as ms3:
        ms3.exceptions.NoSuchKey = DummyEx
        logs = GlobalAuditService.get_form_logs("email")
        assert logs == []

def test_get_form_logs_other_exception():
    class NotNoSuchKey(Exception):
        pass
    with patch("app.services.global_audit_service.get_logs", side_effect=NotNoSuchKey("fail")), \
         patch("app.services.global_audit_service.s3_client") as ms3:
        class DummyEx(Exception):
            pass
        ms3.exceptions.NoSuchKey = DummyEx
        with pytest.raises(HTTPException) as exc:
            GlobalAuditService.get_form_logs("email")
        assert exc.value.status_code == 500
        assert "Failed to fetch form audit logs" in str(exc.value.detail)

def test_get_document_logs_by_id():
    with patch.object(GlobalAuditService, "get_document_logs", return_value=[{"entity_id": "doc1"}, {"entity_id": "doc2"}]):
        logs = GlobalAuditService.get_document_logs_by_id("email", "doc1")
        assert logs == [{"entity_id": "doc1"}]

def test_get_document_logs_by_id_empty():
    with patch.object(GlobalAuditService, "get_document_logs", return_value=[]):
        logs = GlobalAuditService.get_document_logs_by_id("email", "doc1")
        assert logs == []

def test_get_form_logs_by_id():
    with patch.object(GlobalAuditService, "get_form_logs", return_value=[{"entity_id": "fid1"}, {"entity_id": "fid2"}]):
        logs = GlobalAuditService.get_form_logs_by_id("email", "fid2")
        assert logs == [{"entity_id": "fid2"}]

def test_get_form_logs_by_id_empty():
    with patch.object(GlobalAuditService, "get_form_logs", return_value=[]):
        logs = GlobalAuditService.get_form_logs_by_id("email", "fid2")
    assert logs == []
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from app.services.global_audit_service import GlobalAuditService

email = "user@example.com"
form_id = "form123"
doc_id = "doc123"
actor = {"id": "user1", "name": "Test User"}
metadata = {"field": "value"}
targets = [{"id": "party1"}]

@patch("app.services.global_audit_service.append_logs")
def test_log_form_action_success(mock_append):
    GlobalAuditService.log_form_action(email, form_id, "submitted", actor, metadata, targets)
    expected_key = f"{email}/audit/all_logs_form.json"
    assert mock_append.called
    args, kwargs = mock_append.call_args
    assert args[1] == expected_key

@patch("app.services.global_audit_service.append_logs", side_effect=Exception("S3 Error"))
def test_log_form_action_failure(mock_append):
    with pytest.raises(HTTPException) as exc:
        GlobalAuditService.log_form_action(email, form_id, "submitted", actor)
    assert exc.value.status_code == 500
    assert "Failed to write audit log" in exc.value.detail

@patch("app.services.global_audit_service.append_logs")
def test_log_document_action_success(mock_append):
    GlobalAuditService.log_document_action(email, doc_id, "signed", actor)
    expected_key = f"{email}/audit/all_logs_document.json"
    args, kwargs = mock_append.call_args
    assert args[1] == expected_key

@patch("app.services.global_audit_service.get_logs")
def test_get_document_logs_success(mock_get_logs):
    mock_get_logs.return_value = [{"entity_id": doc_id}]
    logs = GlobalAuditService.get_document_logs(email)
    assert isinstance(logs, list)

@patch("app.services.global_audit_service.get_logs", side_effect=Exception("S3 Failure"))
def test_get_document_logs_error(mock_get_logs):
    with pytest.raises(HTTPException) as exc:
        GlobalAuditService.get_document_logs(email)
    assert exc.value.status_code == 500

@patch("app.services.global_audit_service.get_logs", return_value=[{"entity_id": doc_id}])
def test_get_document_logs_by_id(mock_get_logs):
    logs = GlobalAuditService.get_document_logs_by_id(email, doc_id)
    assert logs == [{"entity_id": doc_id}]

@patch("app.services.global_audit_service.get_logs", return_value=[{"entity_id": form_id}])
def test_get_form_logs_by_id(mock_get_logs):
    logs = GlobalAuditService.get_form_logs_by_id(email, form_id)
    assert logs == [{"entity_id": form_id}]
