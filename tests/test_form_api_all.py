import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.api.routes.form_api import router
from fastapi import FastAPI

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
    return TestClient(app)

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
