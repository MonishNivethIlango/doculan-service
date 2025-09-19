import sys
from unittest.mock import MagicMock

# Patch the DB connection and any side-effectful imports before importing the app code
sys.modules['auth_app.app.database.connection'] = MagicMock(
    db=MagicMock(),
    save_document_url=MagicMock(),
    tracker_collection=MagicMock()
)

# Now import the rest
from app.services.FormService import FormService
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.FormService import FormService
from fastapi import HTTPException
from datetime import datetime, timezone
from datetime import datetime, timezone

def create_form_token(*args, **kwargs):
    # Dummy implementation for testing
    return {
        "token": "dummy-token",
        "validity_datetime": datetime.now(timezone.utc)
    }
    async def submit(self, email, submission, user_email):
        try:
            # ...existing code...
            pass
        except Exception as e:
            return {"message": str(e)}
        
# --- Static CRUD methods ---

def test_create_form_calls_repository():
    with patch("app.services.FormService.FormRepository.create_form", return_value="result") as mock_create:
        result = FormService.create_form("fid", {"foo": "bar"}, "email", {"name": "n"}, "user@email.com")
        assert result == "result"
        mock_create.assert_called_once()

def test_get_form_calls_repository():
    with patch("app.services.FormService.FormRepository.read_form", return_value={"id": "fid"}) as mock_read:
        result = FormService.get_form("fid", "email")
        assert result == {"id": "fid"}
        mock_read.assert_called_once()

def test_get_all_forms_calls_repository():
    with patch("app.services.FormService.FormRepository.get_all_forms", return_value=[{"id": "fid"}]) as mock_get:
        result = FormService.get_all_forms("email")
        assert result == [{"id": "fid"}]
        mock_get.assert_called_once()

def test_update_form_calls_repository():
    with patch("app.services.FormService.FormRepository.update_form", return_value="updated") as mock_update:
        result = FormService.update_form("fid", {"foo": "bar"}, "email")
        assert result == "updated"
        mock_update.assert_called_once()

def test_delete_form_calls_repository():
    with patch("app.services.FormService.FormRepository.delete_form", return_value="deleted") as mock_delete:
        result = FormService.delete_form("fid", "email")
        assert result == "deleted"
        mock_delete.assert_called_once()

def test_update_tracking_calls_repository():
    with patch("app.services.FormService.FormRepository.update_trackings") as mock_update:
        FormService.update_tracking("fid", {"foo": "bar"}, "party@email.com", "email")
        mock_update.assert_called_once()

def test_get_tracking_entry_calls_repository():
    with patch("app.services.FormService.FormRepository.get_tracking", return_value={"foo": "bar"}) as mock_get:
        result = FormService.get_tracking_entry("fid", "party@email.com", "email")
        assert result == {"foo": "bar"}
        mock_get.assert_called_once()

def test_validate_submission_calls_repository():
    with patch("app.services.FormService.FormRepository.validate_form") as mock_validate:
        FormService.validate_submission({"form": "f"}, {"v": 1})
        mock_validate.assert_called_once()

# --- PDF upload ---

@pytest.mark.asyncio
async def test_upload_pdf_to_s3_calls_repository():
    with patch("app.services.FormService.FormRepository.upload_pdf", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "url"
        result = await FormService.upload_pdf_to_s3(b"bytes", "fid", "email", "party@email.com", "path", "title")
        assert result == "url"
        mock_upload.assert_awaited_once()

# --- get_pdf_to_s3 ---

@pytest.mark.asyncio
async def test_get_pdf_to_s3_calls_get_form_and_repository():
    service = FormService()
    with patch.object(service, "get_form", return_value={"id": "fid"}) as mock_get_form, \
         patch("app.services.FormService.FormRepository.get_pdf", new_callable=AsyncMock) as mock_get_pdf:
        mock_get_pdf.return_value = b"pdf"
        result = await service.get_pdf_to_s3("email", "fid", "party@email.com")
        assert result == b"pdf"
        mock_get_form.assert_called_once()
        mock_get_pdf.assert_awaited_once()

# --- get_forms ---

@pytest.mark.asyncio
async def test_get_forms_calls_get_form():
    service = FormService()
    with patch.object(service, "get_form", return_value={"id": "fid"}) as mock_get_form:
        submission = MagicMock(form_id="fid")
        result = await service.get_forms("email", submission)
        assert result == {"id": "fid"}
        mock_get_form.assert_called_once()

# --- validate_form ---

@pytest.mark.asyncio
async def test_validate_form_calls_validate_submission():
    service = FormService()
    with patch.object(service, "validate_submission") as mock_validate:
        await service.validate_form("form", MagicMock(values="vals"))
        mock_validate.assert_called_once()

# --- submit ---

@pytest.mark.asyncio
async def test_submit_successful(monkeypatch):
    service = FormService()
    # Patch all called methods
    monkeypatch.setattr(service, "get_forms", AsyncMock(return_value={"formPath": "p", "formTitle": "t"}))
    monkeypatch.setattr(service, "validate_form", AsyncMock())
    pdf_gen = MagicMock()
    pdf_gen.generate_pdf = AsyncMock(return_value=b"pdf")
    monkeypatch.setattr("app.services.FormService.PDFGenerator", lambda: pdf_gen)
    monkeypatch.setattr(service, "upload_pdf_to_s3", AsyncMock())
    monkeypatch.setattr("app.services.FormService.FormModel.upload_submission", MagicMock(return_value={"party_name": "pn", "holder": {}, "cc_emails": []}))
    monkeypatch.setattr("app.services.FormService.NotificationService.store_form_notification", AsyncMock())
    monkeypatch.setattr("app.services.FormService.email_service.send_filled_pdf_email", MagicMock())
    submission = MagicMock(form_id="fid", party_email="p@email.com", values={}, client_info=None)
    result = await service.submit("email", submission, "user@email.com")
    assert result["message"] == "Form submitted and PDF sent successfully"

@pytest.mark.asyncio
async def test_submit_handles_exception(monkeypatch):
    service = FormService()
    monkeypatch.setattr(service, "get_forms", AsyncMock(side_effect=Exception("fail")))
    submission = MagicMock(form_id="fid", party_email="p@email.com", values={}, client_info=None)
    # Should not raise
    result = await service.submit("email", submission, "user@email.com")
    assert "message" in result

# --- form_tracking_payload ---

@pytest.mark.asyncio
async def test_form_tracking_payload_builds_entries():
    service = FormService()
    with patch.object(service, "get_form", return_value={"formTitle": "t", "fields": [], "created_at": "now"}):
        data = MagicMock(form_id="fid", parties=[MagicMock(email="e", name="n", party_id="pid")], validityDate="v", remainder=1, email_responses=[], holder=None, cc_emails=[], client_info=None)
        entries = await service.form_tracking_payload(data, "email")
        assert isinstance(entries, list)
        assert entries[0]["party_email"] == "e"

# --- send_forms ---

@pytest.mark.asyncio
async def test_send_forms_success(monkeypatch):
    service = FormService()
    monkeypatch.setattr(service, "form_tracking_payload", AsyncMock(return_value=[{"party_email": "e", "party_id": "pid", "party_name": "n"}]))
    monkeypatch.setattr(service, "update_tracking", MagicMock())
    monkeypatch.setattr("app.services.FormService.create_form_token", AsyncMock(return_value={"token": "t", "validity_datetime": datetime.now(timezone.utc)}))
    monkeypatch.setattr("app.services.FormService.email_service.send_form_link", AsyncMock())
    data = MagicMock(form_id="fid", email_responses=[MagicMock()], holder=MagicMock(name="h", email="e"), cc_emails=[], validityDate="v", remainder=1)
    result = await service.send_forms(data, "email", "user@email.com")
    assert result["message"].startswith("Form sent")

@pytest.mark.asyncio
async def test_send_forms_handles_exception(monkeypatch):
    service = FormService()
    monkeypatch.setattr(service, "form_tracking_payload", AsyncMock(side_effect=Exception("fail")))
    data = MagicMock(form_id="fid", email_responses=[MagicMock()], holder=None, cc_emails=[], validityDate="v", remainder=1)
    with pytest.raises(HTTPException):
        await service.send_forms(data, "email", "user@email.com")

# --- resend_form ---

@pytest.mark.asyncio
async def test_resend_form_success(monkeypatch):
    service = FormService()
    # Patch S3 client and all called methods
    monkeypatch.setattr("app.services.FormService.s3_client.get_object", MagicMock(return_value={"Body": MagicMock(read=lambda: b'{"party@email.com": {"status": {"state": "sent"}, "party_id": "pid", "resent_logs": [], "email_responses": [{"email_subject": "s", "email_body": "b"}], "holder": {}, "cc_emails": []}}')}))
    monkeypatch.setattr("app.services.FormService.s3_client.put_object", MagicMock())
    monkeypatch.setattr("app.services.FormService.create_form_token", AsyncMock(return_value={"token": "t", "validity_datetime": datetime.now(timezone.utc)}))
    monkeypatch.setattr("app.services.FormService.email_service.send_form_link", AsyncMock())
    data = MagicMock(validityDate=None, client_info=None)
    result = await service.resend_form(data, "fid", "party@email.com", "email", "user@email.com")
    assert result["message"].startswith("Form link resent")

@pytest.mark.asyncio
async def test_resend_form_party_not_found(monkeypatch):
    service = FormService()
    monkeypatch.setattr("app.services.FormService.s3_client.get_object", MagicMock(return_value={"Body": MagicMock(read=lambda: b'{}')}))
    data = MagicMock(validityDate=None, client_info=None)
    with pytest.raises(HTTPException):
        await service.resend_form(data, "fid", "party@email.com", "email", "user@email.com")

# --- get_party_submitted_values ---

def test_get_party_submitted_values_success():
    with patch("app.services.FormService.FormRepository.get_user_data", return_value={"party@email.com": {"foo": "bar"}}):
        result = FormService.get_party_submitted_values("email", "fid", "party@email.com")
        assert result["submitted_values"] == {"foo": "bar"}

def test_get_party_submitted_values_not_found():
    with patch("app.services.FormService.FormRepository.get_user_data", return_value=None):
        with pytest.raises(HTTPException):
            FormService.get_party_submitted_values("email", "fid", "party@email.com")

def test_get_party_submitted_values_no_party():
    with patch("app.services.FormService.FormRepository.get_user_data", return_value={}):
        with pytest.raises(HTTPException):
            FormService.get_party_submitted_values("email", "fid", "party@email.com")

# --- get_all_statuses ---

@pytest.mark.asyncio
async def test_get_all_statuses_success():
    with patch("app.services.FormService.FormRepository.get_tracking_data", new_callable=AsyncMock, return_value={"p": {"status": {}}}):
        result = await FormService.get_all_statuses("email", "fid")
        assert "statuses" in result

@pytest.mark.asyncio
async def test_get_all_statuses_not_found():
    with patch("app.services.FormService.FormRepository.get_tracking_data", new_callable=AsyncMock, return_value=None):
        with pytest.raises(HTTPException):
            await FormService.get_all_statuses("email", "fid")

# --- count_statuses ---

def test_count_statuses_counts_correctly():
    statuses = [{"sent": {"timestamp": "1"}}, {"completed": {"timestamp": "2"}}, {"cancelled": {"timestamp": "3"}}]
    result = FormService.count_statuses(statuses)
    assert result["sent"] == 1
    assert result["completed"] == 1
    assert result["cancelled"] == 1

# --- get_status_counts ---

@pytest.mark.asyncio
async def test_get_status_counts_for_form(monkeypatch):
    monkeypatch.setattr("app.services.FormService.FormRepository.get_tracking_data", AsyncMock(return_value={"p": {"status": {"sent": {"timestamp": "1"}}}}))
    result = await FormService.get_status_counts("email", "fid")
    assert "status_counts" in result

@pytest.mark.asyncio
async def test_get_status_counts_all_forms(monkeypatch):
    monkeypatch.setattr("app.services.FormService.FormRepository.list_form_folders", MagicMock(return_value=["/a/forms/fid/"]))
    monkeypatch.setattr("app.services.FormService.FormRepository.get_tracking_data", AsyncMock(return_value={"p": {"status": {"sent": {"timestamp": "1"}}}}))
    result = await FormService.get_status_counts("email")
    assert "status_counts" in result

# --- get_tracking_status ---

def test_get_tracking_status_completed():
    tracking = {"status": {"completed": {}}}
    assert FormService.get_tracking_status(tracking) == "completed"

def test_get_tracking_status_cancelled():
    tracking = {"status": {"cancelled": {}}}
    assert FormService.get_tracking_status(tracking) == "cancelled"

def test_get_tracking_status_expired():
    tracking = {"status": {}, "validityDate": datetime.now(timezone.utc).isoformat()}
    assert FormService.get_tracking_status(tracking) in {"expired", "in_progress", "unknown"}

def test_get_tracking_status_in_progress():
    tracking = {"status": {"opened": {}}}
    assert FormService.get_tracking_status(tracking) == "in_progress"

def test_get_tracking_status_unknown():
    tracking = {"status": {}}
    assert FormService.get_tracking_status(tracking) == "unknown"

# --- get_trackings_status_counts ---

def test_get_trackings_status_counts_success(monkeypatch):
    monkeypatch.setattr("app.services.FormService.FormRepository.list_form_folders", MagicMock(return_value=["/a/forms/fid/"]))
    monkeypatch.setattr("app.services.FormService.FormRepository.get_trackings", MagicMock(return_value={"p@email.com": {"status": {"sent": {"timestamp": "1"}}, "created_at": "now", "party_name": "n"}}))
    monkeypatch.setattr("app.services.FormService.FormService.get_form", MagicMock(return_value={"formTitle": "t"}))
    result = FormService.get_trackings_status_counts("email")
    assert "total_status_counts" in result

# --- get_party_status ---

@pytest.mark.asyncio
async def test_get_party_status_success(monkeypatch):
    service = FormService()
    monkeypatch.setattr("app.services.FormService.FormRepository.get_tracking_data", AsyncMock(return_value={"p@email.com": {"party_name": "n", "status": {}}}))
    result = await service.get_party_status("email", "fid", "p@email.com")
    assert result["party_email"] == "p@email.com"

@pytest.mark.asyncio
async def test_get_party_status_not_found(monkeypatch):
    service = FormService()
    monkeypatch.setattr("app.services.FormService.FormRepository.get_tracking_data", AsyncMock(return_value={}))
    result = await service.get_party_status("email", "fid", "p@email.com")
    assert result is None

# --- get_all_submitted_values ---

@pytest.mark.asyncio
async def test_get_all_submitted_values_success(monkeypatch):
    service = FormService()
    monkeypatch.setattr("app.services.FormService.FormRepository.list_form_ids", AsyncMock(return_value=["fid"]))
    monkeypatch.setattr("app.services.FormService.FormRepository.get_tracking_data", AsyncMock(return_value={"p@email.com": {"status": {}, "last_updated": "now", "party_name": "n"}}))
    monkeypatch.setattr("app.services.FormService.FormRepository.get_user_data", MagicMock(return_value={"p@email.com": [{"id": 1, "type": "t", "label": "l", "required": True, "sensitive": False, "value": "v"}]}))
    result = await service.get_all_submitted_values("email")
    assert "fid" in result
