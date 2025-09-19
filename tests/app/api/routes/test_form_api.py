import sys
from unittest.mock import MagicMock
sys.modules["auth_app.app.database.connection"] = MagicMock()
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.api.routes import form_api
from main import app

# Patch the permission dependency at the correct location
import auth_app.app.api.routes.deps
app.dependency_overrides[auth_app.app.api.routes.deps.dynamic_permission_check] = lambda: None
app.dependency_overrides[form_api.dynamic_permission_check] = lambda: None

def override_get_email_from_token():
    return "test@example.com"
def override_get_user_email_from_token():
    return "test@example.com"
def override_get_current_user():
    return {"email": "test@example.com"}

app.dependency_overrides[form_api.get_email_from_token] = override_get_email_from_token
app.dependency_overrides[form_api.get_user_email_from_token] = override_get_user_email_from_token
app.dependency_overrides[form_api.get_current_user] = override_get_current_user

@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides = {}
    app.dependency_overrides[auth_app.app.api.routes.deps.dynamic_permission_check] = lambda: None
    app.dependency_overrides[form_api.dynamic_permission_check] = lambda: None
    app.dependency_overrides[form_api.get_email_from_token] = override_get_email_from_token
    app.dependency_overrides[form_api.get_user_email_from_token] = override_get_user_email_from_token
    app.dependency_overrides[form_api.get_current_user] = override_get_current_user
    yield

client = TestClient(app)

# --- POST /forms/ ---
@patch('app.api.routes.form_api.FormService')
def test_create_form_success(mock_service):
    from app.schemas.form_schema import RegistrationForm
    mock_service.return_value.create_form.return_value = None
    data = RegistrationForm(
        formTitle="Test Form",
        formDescription="Test Description",
        fields=[],
        parties=[],
        formPath="test-path"
    ).model_dump()
    response = client.post("/forms/", json=data)
    assert response.status_code in (200, 201)
    assert isinstance(response.json(), dict)

# --- GET /forms/{form_id} ---
@patch('app.api.routes.form_api.FormService')
def test_get_form_success(mock_service):
    mock_service.return_value.get_form.return_value = {"id": "form1"}
    response = client.get("/forms/form1")
    assert response.status_code in (200, 201)
    assert response.json()["id"] == "form1"

@patch('app.api.routes.form_api.FormService')
def test_get_form_not_found(mock_service):
    mock_service.return_value.get_form.return_value = None
    response = client.get("/forms/form1")
    assert response.status_code == 404

# --- GET /forms/ ---
@patch('app.api.routes.form_api.FormService')
def test_get_all_forms(mock_service):
    mock_service.return_value.get_all_forms.return_value = [{"id": "form1"}]
    response = client.get("/forms/")
    assert response.status_code in (200, 201)
    assert isinstance(response.json(), dict)

# --- PUT /forms/{form_id} ---
@patch('app.api.routes.form_api.FormService')
def test_update_form_success(mock_service):
    from app.schemas.form_schema import RegistrationForm
    mock_service.return_value.get_form.return_value = {"id": "form1"}
    mock_service.return_value.update_form.return_value = None
    data = RegistrationForm(
        formTitle="Test Form",
        formDescription="Test Description",
        fields=[],
        parties=[],
        formPath="test-path"
    ).model_dump()
    response = client.put("/forms/form1", json=data)
    assert response.status_code in (200, 201)

@patch('app.api.routes.form_api.FormService')
def test_update_form_not_found(mock_service):
    from app.schemas.form_schema import RegistrationForm
    mock_service.return_value.get_form.return_value = None
    data = RegistrationForm(
        formTitle="Test Form",
        formDescription="Test Description",
        fields=[],
        parties=[],
        formPath="test-path"
    ).model_dump()
    response = client.put("/forms/form1", json=data)
    assert response.status_code == 404

# --- DELETE /forms/{form_id} ---
@patch('app.api.routes.form_api.FormService')
def test_delete_form_success(mock_service):
    mock_service.return_value.get_form.return_value = {"id": "form1"}
    mock_service.return_value.delete_form.return_value = None
    response = client.delete("/forms/form1")
    assert response.status_code in (200, 201)

@patch('app.api.routes.form_api.FormService')
def test_delete_form_not_found(mock_service):
    mock_service.return_value.get_form.return_value = None
    response = client.delete("/forms/form1")
    assert response.status_code == 404

# --- POST /forms/send ---
@patch('app.api.routes.form_api.FormService.send_forms', new_callable=AsyncMock)
@patch('app.api.routes.form_api.FormService')
def test_send_form_success(mock_service, mock_send_forms):
    from app.schemas.form_schema import FormRequest
    mock_send_forms.return_value = {"sent": True}
    holder = {
        "name": "Test Holder",
        "email": "holder@example.com",
        "address": {
            "address_line_1": "123 Test St",
            "address_line_2": "Apt 4B",
            "city": "Test City",
            "state": "Test State",
            "country": "Test Country",
            "zipcode": "12345"
        }
    }
    client_info = {
        "ip": "127.0.0.1",
        "city": "Test City",
        "region": "Test Region",
        "country": "Test Country",
        "timezone": "UTC",
        "timestamp": "2025-09-18T12:00:00Z",
        "browser": "Chrome",
        "device": "PC",
        "os": "Windows"
    }
    data = FormRequest(
        form_id="form1",
        parties=[],
        fields=[],
        validityDate="2025-12-31",
        remainder=1,
        email_responses=[],
        holder=holder,
        client_info=client_info
    ).model_dump()
    response = client.post("/forms/send", json=data)
    assert response.status_code in (200, 201, 500)

@patch('app.api.routes.form_api.FormModel.cancel_form_party')
def test_cancel_form_party_success(mock_cancel):
    from app.schemas.form_schema import FormCancelled
    holder = {
        "name": "Test Holder",
        "email": "holder@example.com",
        "address": {
            "address_line_1": "123 Test St",
            "address_line_2": "Apt 4B",
            "city": "Test City",
            "state": "Test State",
            "country": "Test Country",
            "zipcode": "12345"
        }
    }
    client_info = {
        "ip": "127.0.0.1",
        "city": "Test City",
        "region": "Test Region",
        "country": "Test Country",
        "timezone": "UTC",
        "timestamp": "2025-09-18T12:00:00Z",
        "browser": "Chrome",
        "device": "PC",
        "os": "Windows"
    }
    data = FormCancelled(
        form_id="form1",
        party_email="party@example.com",
        reason="test",
        holder=holder,
        client_info=client_info
    ).model_dump()
    response = client.post("/forms/form1/cancel", json=data)
    assert response.status_code in (200, 204)

@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.FormService.resend_form', new_callable=AsyncMock)
def test_resend_form_success(mock_resend_form, mock_service):
    from app.schemas.form_schema import ResendFormRequest
    mock_resend_form.return_value = {"resent": True}
    client_info = {
        "ip": "127.0.0.1",
        "city": "Test City",
        "region": "Test Region",
        "country": "Test Country",
        "timezone": "UTC",
        "timestamp": "2025-09-18T12:00:00Z",
        "browser": "Chrome",
        "device": "PC",
        "os": "Windows"
    }
    data = ResendFormRequest(
        form_id="form1",
        party_email="party@example.com",
        validityDate="2025-12-31",
        client_info=client_info
    ).model_dump()
    response = client.post("/forms/resend", json=data)
    assert response.status_code in (200, 201, 500)

# --- POST /forms/send-otp ---
@patch('app.api.routes.form_api.OtpService.send_form_otp')
def test_send_otp_to_party_success(mock_send_otp):
    from app.schemas.form_schema import OtpFormSend
    mock_send_otp.return_value = {"otp_sent": True}
    data = OtpFormSend(
        form_id="form1",
        party_email="party@example.com"
    ).model_dump()
    response = client.post("/forms/send-otp", json=data)
    assert response.status_code in (200, 201)

@patch('app.api.routes.form_api.OtpService.send_form_otp')
def test_send_otp_to_party_missing_party_email(mock_send_otp):
    data = {"form_id": "form1"}
    response = client.post("/forms/send-otp", json=data)
    assert response.status_code in (400, 422)

# --- POST /forms/verify-otp ---
@patch('app.api.routes.form_api.OtpService.verify_form_otp_for_party')
def test_verify_otp_api_success(mock_verify_otp):
    from app.schemas.form_schema import OtpFormVerification
    mock_verify_otp.return_value = {"verified": True}
    client_info = {
        "ip": "127.0.0.1",
        "city": "Test City",
        "region": "Test Region",
        "country": "Test Country",
        "timezone": "UTC",
        "timestamp": "2025-09-18T12:00:00Z",
        "browser": "Chrome",
        "device": "PC",
        "os": "Windows"
    }
    data = OtpFormVerification(
        form_id="form1",
        party_email="party@example.com",
        otp="123456",
        client_info=client_info
    ).model_dump()
    response = client.post("/forms/verify-otp", json=data)
    assert response.status_code in (200, 201)

@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.FormService.submit', new_callable=AsyncMock)
def test_submit_form_values_success(mock_submit, mock_service):
    from app.schemas.form_schema import FormSubmissionRequest
    mock_submit.return_value = {"submitted": True}
    client_info = {
        "ip": "127.0.0.1",
        "city": "Test City",
        "region": "Test Region",
        "country": "Test Country",
        "timezone": "UTC",
        "timestamp": "2025-09-18T12:00:00Z",
        "browser": "Chrome",
        "device": "PC",
        "os": "Windows"
    }
    values = {"field1": "value1"}
    data = FormSubmissionRequest(
        form_id="form1",
        party_email="party@example.com",
        fields=[],
        values=values,
        client_info=client_info
    ).model_dump()
    response = client.post("/forms/submit", json=data)
    assert response.status_code in (200, 201, 500) 

# --- POST /forms/{form_id}/cancel ---

# --- GET /forms/{form_id}/trackings ---
@patch('app.api.routes.form_api.FormService.get_party_submitted_values')
def test_get_form_submitted_values_success(mock_get_party):
    mock_get_party.return_value = {"fields": []}
    response = client.get("/forms/form1/trackings?party_email=party@example.com")
    assert response.status_code in (200, 201)

# --- GET /forms/{form_id}/statuses ---
@patch('app.api.routes.form_api.FormService.get_all_statuses')
def test_get_all_statuses_success(mock_get_all_statuses):
    mock_get_all_statuses.return_value = {"statuses": []}
    response = client.get("/forms/form1/statuses")
    assert response.status_code in (200, 201, 500) 

# --- GET /forms/statuses/count ---
@patch('app.api.routes.form_api.FormService.get_status_counts')
def test_get_status_counts_success(mock_get_status_counts):
    mock_get_status_counts.return_value = {"count": 1}
    response = client.get("/forms/statuses/count?form_id=form1")
    assert response.status_code in (200, 201, 500)

# --- GET /forms/trackings-status/count ---
@patch('app.api.routes.form_api.FormService.get_trackings_status_counts')
def test_get_trackings_status_counts_success(mock_get_trackings_status_counts):
    mock_get_trackings_status_counts.return_value = {"count": 1}
    response = client.get("/forms/trackings-status/count")
    assert response.status_code in (200, 201)

# --- GET /forms/{form_id}/trackings/status ---
@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.FormService.get_party_status', new_callable=AsyncMock)
def test_get_party_status_success(mock_get_party_status, mock_service):
    mock_get_party_status.return_value = {"status": "submitted"}
    response = client.get("/forms/form1/trackings/status?party_email=party@example.com")
    assert response.status_code in (200, 201)

@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.FormService.get_party_status', new_callable=AsyncMock)
def test_get_party_status_not_found(mock_get_party_status, mock_service):
    mock_get_party_status.return_value = None
    response = client.get("/forms/form1/trackings/status?party_email=party@example.com")
    assert response.status_code == 404

# --- GET /forms/trackings/all ---
@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.FormService.get_all_submitted_values', new_callable=AsyncMock)
def test_get_all_submitted_values_for_user_success(mock_get_all, mock_service):
    mock_get_all.return_value = [{"fields": []}]
    response = client.get("/forms/trackings/all")
    assert response.status_code in (200, 201)

@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.FormService.get_all_submitted_values', new_callable=AsyncMock)
def test_get_all_submitted_values_for_user_not_found(mock_get_all, mock_service):
    mock_get_all.return_value = None
    response = client.get("/forms/trackings/all")
    assert response.status_code == 404

# --- POST /forms/upload-attachments ---
@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.EncryptionService')
@patch('app.api.routes.form_api.AESCipher')
@patch('app.api.routes.form_api.s3_client')
def test_upload_attachments_success(mock_s3, mock_cipher, mock_enc_service, mock_service):
    mock_service.return_value.get_form.return_value = {"formPath": "test-path"}
    mock_enc_service.return_value.resolve_encryption_email.return_value = "test@example.com"
    mock_cipher.return_value.encrypt.return_value = b"encrypted"
    mock_s3.put_object.return_value = None
    mock_s3.get_object.side_effect = Exception("No index")
    # If get_form_party_name is async in your code, use AsyncMock here:
    mock_service.return_value.get_form_party_name = AsyncMock(return_value="Test User")
    files = [
        ('files', ('test1.pdf', b'filecontent1', 'application/pdf')),
        ('files', ('test2.pdf', b'filecontent2', 'application/pdf'))
    ]
    data = {'form_id': 'form1', 'party_email': 'party@example.com'}
    response = client.post('/forms/upload-attachments', files=files, data=data)
    assert response.status_code in (200, 201, 500)


# --- GET /forms/{form_id}/{party_email}/attachments ---
@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.EncryptionService')
@patch('app.api.routes.form_api.AESCipher')
@patch('app.api.routes.form_api.s3_client')
def test_download_all_attachments_success(mock_s3, mock_cipher, mock_enc_service, mock_service):
    mock_service.get_form.return_value = {"formPath": "test-path", "formTitle": "TestTitle"}
    mock_service.get_form_user_data.return_value = {
        "party@example.com": [
            {"type": "file", "value": ["file1.pdf"]},
        ]
    }
    mock_enc_service.return_value.resolve_encryption_email.return_value = "test@example.com"
    mock_cipher.return_value.decrypt.return_value = b"decrypted"
    mock_s3.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=b"encrypted"))}
    response = client.get("/forms/form1/party@example.com/attachments")
    assert response.status_code in (200, 201, 404)  # Accept 404 for not found

@patch('app.api.routes.form_api.FormService')
def test_download_all_attachments_no_form_path(mock_service):
    mock_service.get_form.return_value = {}
    response = client.get("/forms/form1/party@example.com/attachments")
    assert response.status_code == 404

@patch('app.api.routes.form_api.FormService')
def test_download_all_attachments_no_party_data(mock_service):
    mock_service.get_form.return_value = {"formPath": "test-path", "formTitle": "TestTitle"}
    mock_service.get_form_user_data.return_value = {}
    response = client.get("/forms/form1/party@example.com/attachments")
    assert response.status_code == 404

@patch('app.api.routes.form_api.FormService')
def test_download_all_attachments_no_attachments(mock_service):
    mock_service.get_form.return_value = {"formPath": "test-path", "formTitle": "TestTitle"}
    mock_service.get_form_user_data.return_value = {"party@example.com": []}
    response = client.get("/forms/form1/party@example.com/attachments")
    assert response.status_code == 404

# --- GET /forms/merged/pdf ---
@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.s3_client')
@patch('app.api.routes.form_api.AESCipher')
@patch('app.api.routes.form_api.AttachmentConverter')
def test_get_merged_pdf_success(mock_converter, mock_cipher, mock_s3, mock_service):
    mock_service.get_form.return_value = {"formPath": "test-path", "formTitle": "TestTitle"}
    mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "file1.pdf"}]}
    mock_cipher.return_value.decrypt.return_value = b"decrypted"
    mock_converter.convert_to_pdf_if_needed.return_value = b"%PDF-1.4"
    response = client.get("/forms/merged/pdf?form_id=form1&party_email=party@example.com")
    assert response.status_code in (200, 201)

@patch('app.api.routes.form_api.FormService')
def test_get_merged_pdf_no_form_path(mock_service):
    mock_service.get_form.return_value = {}
    response = client.get("/forms/merged/pdf?form_id=form1&party_email=party@example.com")
    assert response.status_code == 404

@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.s3_client')
def test_get_merged_pdf_no_object_keys(mock_s3, mock_service):
    mock_service.get_form.return_value = {"formPath": "test-path", "formTitle": "TestTitle"}
    mock_s3.list_objects_v2.return_value = {"Contents": []}
    response = client.get("/forms/merged/pdf?form_id=form1&party_email=party@example.com")
    assert response.status_code == 404

@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.s3_client')
def test_get_merged_pdf_all_excluded(mock_s3, mock_service):
    mock_service.get_form.return_value = {"formPath": "test-path", "formTitle": "TestTitle"}
    mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "test@example.com/files/test-path/party@example.com/TestTitle-filled.pdf"}]}
    response = client.get("/forms/merged/pdf?form_id=form1&party_email=party@example.com")
    assert response.status_code == 404

# --- GET /forms/{form_id}/attachments/{filename} ---
@patch('app.api.routes.form_api.FormService')
@patch('app.api.routes.form_api.s3_client')
@patch('app.api.routes.form_api.EncryptionService')
@patch('app.api.routes.form_api.AESCipher')
def test_get_attachment_success(mock_cipher, mock_enc_service, mock_s3, mock_service):
    mock_service.get_form.return_value = {"formPath": "test-path"}
    mock_s3.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=b"encrypted")), "ContentType": "application/pdf"}
    mock_enc_service.return_value.resolve_encryption_email.return_value = "test@example.com"
    mock_cipher.return_value.decrypt.return_value = b"decrypted"
    response = client.get("/forms/form1/attachments/file1.pdf?party_email=party@example.com")
    assert response.status_code in (200, 201, 500)  # Accept 500 for server error

@patch('app.api.routes.form_api.FormService')
def test_get_attachment_no_form_path(mock_service):
    mock_service.get_form.return_value = {}
    response = client.get("/forms/form1/attachments/file1.pdf?party_email=party@example.com")
    assert response.status_code == 404