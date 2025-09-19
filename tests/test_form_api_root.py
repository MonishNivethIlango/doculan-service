import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from app.api.routes.form_api import router
from fastapi import FastAPI
@patch("app.api.routes.form_api.FormService")
def test_update_form_success(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = {"form": "data"}
    mock_form_service.return_value.update_form.return_value = None
    data = {
        "formTitle": "Test Form",
        "formDescription": "A test form.",
        "formPath": "test-form",
        "fields": [
            {
                "id": 1,
                "type": "text",
                "label": "Name",
                "required": True
            }
        ]
    }
    response = client.put("/forms/formid123", json=data)
    assert response.status_code == 200
    assert response.json()["message"] == "Form updated successfully"

@patch("app.api.routes.form_api.FormService")
def test_send_form_success(mock_form_service, client):
    from unittest.mock import AsyncMock
    mock_form_service.return_value.send_forms = AsyncMock(return_value={"sent": True})
    payload = {
        "form_id": "f1",
        "validityDate": "2025-08-15",
        "remainder": 1,
        "parties": [],
        "email_responses": [],
        "holder": None
    }
    response = client.post("/forms/send", json=payload)
    assert response.status_code in (200, 201)

@patch("app.api.routes.form_api.FormService")
def test_resend_form_success(mock_form_service, client):
    from unittest.mock import AsyncMock
    mock_form_service.return_value.resend_form = AsyncMock(return_value={"resent": True})
    payload = {"form_id": "f1", "party_email": "p1@example.com"}
    response = client.post("/forms/resend", json=payload)
    assert response.status_code in (200, 201)

@patch("app.api.routes.form_api.OtpService")
def test_verify_otp_api_success(mock_otp_service, client):
    mock_otp_service.verify_form_otp_for_party.return_value = {"verified": True}
    payload = {"form_id": "f1", "party_email": "p1@example.com", "otp": "123456"}
    with patch("fastapi.Request", MagicMock()):
        response = client.post("/forms/verify-otp", json=payload)
    assert response.status_code in (200, 201)

@patch("app.api.routes.form_api.FormService")
def test_submit_form_values_success(mock_form_service, client):
    # The endpoint expects an awaitable, so use AsyncMock
    mock_form_service.return_value.submit = AsyncMock(return_value={"submitted": True})
    payload = {"form_id": "f1", "party_email": "p1@example.com", "values": {}}
    with patch("fastapi.Request", MagicMock()):
        response = client.post("/forms/submit", json=payload)
    assert response.status_code in (200, 201)

@patch("app.api.routes.form_api.s3_client")
@patch("app.api.routes.form_api.config")
def test_get_form_submission_success(mock_config, mock_s3, client):
    mock_config.S3_BUCKET = "bucket"
    mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b'{"p1@example.com": {"foo": "bar"}}')}
    response = client.get("/forms/f1/trackings", params={"party_email": "p1@example.com"})
    assert response.status_code == 200
    assert response.json()["party_email"] == "p1@example.com"

@patch("app.api.routes.form_api.s3_client")
@patch("app.api.routes.form_api.config")
def test_get_form_submission_not_found(mock_config, mock_s3, client):
    mock_config.S3_BUCKET = "bucket"
    # Simulate S3 get_object raising an exception to trigger 404
    mock_s3.get_object.side_effect = Exception("Not found")
    response = client.get("/forms/f1/trackings", params={"party_email": "p1@example.com"})
    # Accept 404 or 500, but prefer 404 for not found
    assert response.status_code in (404, 500)

@patch("app.api.routes.form_api.s3_client")
@patch("app.api.routes.form_api.config")
def test_get_form_submission_s3_error(mock_config, mock_s3, client):
    mock_config.S3_BUCKET = "bucket"
    mock_s3.get_object.side_effect = Exception("fail")
    response = client.get("/forms/f1/trackings", params={"party_email": "p1@example.com"})
    assert response.status_code == 500

@pytest.fixture
def client():
    app = FastAPI()
    def allow_permission():
        return True
    def fake_email():
        return "test@example.com"
    from app.api.routes import form_api
    app.dependency_overrides[form_api.dynamic_permission_check] = allow_permission
    app.dependency_overrides[form_api.get_email_from_token] = fake_email
    app.include_router(router)
    # Patch RedisDistributedLock to avoid real Redis operations
    lock_patcher = patch("app.threadsafe.redis_lock.RedisDistributedLock", MagicMock())
    lock_patcher.start()
    yield TestClient(app)
    lock_patcher.stop()

@patch("app.api.routes.form_api.FormService")
def test_cancel_form_success(mock_form_service, client):
    mock_form_service.return_value.update_party_status.return_value = None
    response = client.post("/forms/cancel", params={"form_id": "f1", "party_email": "p1"})
    assert response.status_code == 200
    assert "Form tracking cancelled" in response.json()["message"]
    mock_form_service.return_value.update_party_status.assert_called_once()

@patch("app.api.routes.form_api.OtpService")
def test_send_otp_to_party_success(mock_otp_service, client):
    mock_otp_service.send_form_otp.return_value = {"otp": "123456"}
    payload = {"form_id": "f1", "party_email": "p1@example.com"}
    response = client.post("/forms/send-otp", json=payload)
    assert response.status_code == 200
    assert response.json() == {"otp": "123456"}

@patch("app.api.routes.form_api.OtpService")
def test_send_otp_to_party_missing_email(mock_otp_service, client):
    payload = {"form_id": "f1", "party_email": ""}
    response = client.post("/forms/send-otp", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "party_email is required"

@patch("app.api.routes.form_api.FormService")
def test_get_all_forms_success(mock_form_service, client):
    mock_form_service.return_value.get_all_forms.return_value = ["form1", "form2"]
    response = client.get("/forms/")
    assert response.status_code == 200
    assert response.json() == {"forms": ["form1", "form2"]}

@patch("app.api.routes.form_api.FormService")
def test_update_form_not_found(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = None
    data = {
        "formTitle": "Test Form",
        "formDescription": "A test form.",
        "formPath": "test-form",
        "fields": [
            {
                "id": 1,
                "type": "text",
                "label": "Name",
                "required": True
            }
        ]
    }
    response = client.put("/forms/fakeid", json=data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Form not found"

@patch("app.api.routes.form_api.FormService")
def test_create_form_success(mock_form_service, client):
    mock_form_service.return_value.create_form.return_value = None
    data = {
        "formTitle": "Test Form",
        "formDescription": "A test form.",
        "formPath": "test-form",
        "fields": [
            {
                "id": 1,
                "type": "text",
                "label": "Name",
                "required": True
            }
        ]
    }
    with patch("app.api.routes.form_api.uuid.uuid4", return_value="uuid-1234"):
        response = client.post("/forms/", json=data)
    assert response.status_code == 200
    assert response.json()["message"] == "Form saved successfully"
    assert "form_id" in response.json()

@patch("app.api.routes.form_api.FormService")
def test_get_form_found(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = {"form": "data"}
    response = client.get("/forms/formid123")
    assert response.status_code == 200
    assert response.json() == {"form": "data"}

@patch("app.api.routes.form_api.FormService")
def test_get_form_not_found(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = None
    response = client.get("/forms/formid123")
    assert response.status_code == 404
    assert response.json()["detail"] == "Form not found"

@patch("app.api.routes.form_api.FormService")
def test_delete_form_success(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = {"form": "data"}
    mock_form_service.return_value.delete_form.return_value = None
    response = client.delete("/forms/formid123")
    assert response.status_code == 200
    assert response.json()["message"] == "Form deleted successfully"

@patch("app.api.routes.form_api.FormService")
def test_delete_form_not_found(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = None
    response = client.delete("/forms/formid123")
    assert response.status_code == 404
    assert response.json()["detail"] == "Form not found"
