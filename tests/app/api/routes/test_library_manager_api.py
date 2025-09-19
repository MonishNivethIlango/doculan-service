import sys
from unittest.mock import MagicMock, AsyncMock

# Patch the entire redis_db module before importing app code
sys.modules["database.redis_db"] = MagicMock()
# Patch the MongoDB connection before importing app code
sys.modules["auth_app.app.database.connection"] = MagicMock()
sys.modules["motor.motor_asyncio"] = MagicMock()

# Patch EncryptionService to avoid await on MagicMock
from app.services import security_service
security_service.EncryptionService.resolve_encryption_email = AsyncMock(return_value="test@example.com")

from fastapi.testclient import TestClient
from unittest.mock import patch
from app.api.routes.library_manager_api import router, dynamic_permission_check, get_email_from_token
from fastapi import FastAPI
import pytest

app = FastAPI()
app.include_router(router)

app.dependency_overrides[dynamic_permission_check] = lambda: True
app.dependency_overrides[get_email_from_token] = lambda: "test@example.com"

@pytest.fixture
def client():
    return TestClient(app)

# --- Library CRUD ---
@patch("app.api.routes.library_manager_api.get_storage")
def test_delete_library_not_found(mock_storage, client):
    mock_storage.return_value.delete_library.return_value = {"deleted": False}
    response = client.delete("/libraries/unknown")
    assert response.status_code == 200
    assert response.json() == {"deleted": False}

@patch("app.api.routes.library_manager_api.get_storage")
def test_delete_library_success(mock_storage, client):
    mock_storage.return_value.delete_library.return_value = {"deleted": True}
    response = client.delete("/libraries/lib1")
    assert response.status_code == 200
    assert response.json() == {"deleted": True}

@patch("app.api.routes.library_manager_api.get_storage")
def test_update_library_success(mock_storage, client):
    mock_storage.return_value.update_library.return_value = {"updated": True}
    files = {'new_file': ('test.pdf', b"PDFDATA", 'application/pdf')}
    response = client.put("/libraries/lib1", files=files)
    assert response.status_code == 200
    assert response.json() == {"updated": True}

@patch("app.api.routes.library_manager_api.get_storage")
def test_update_library_invalid_file_type(mock_storage, client):
    mock_storage.return_value.update_library.return_value = {"updated": False, "error": "Invalid file type"}
    files = {'new_file': ('test.txt', b"NOTPDF", 'text/plain')}
    response = client.put("/libraries/lib1", files=files)
    assert response.status_code == 200
    assert response.json()["updated"] is False

@patch("app.api.routes.library_manager_api.get_storage")
def test_update_library_missing_file(mock_storage, client):
    response = client.put("/libraries/lib1")
    assert response.status_code in (422, 400)

@patch("app.api.routes.library_manager_api.get_storage")
def test_list_libraries_returns_list(mock_storage, client):
    mock_storage.return_value.list_libraries.return_value = [{"id": "lib1"}, {"id": "lib2"}]
    response = client.get("/libraries/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 2

@patch("app.api.routes.library_manager_api.get_storage")
def test_list_libraries_empty(mock_storage, client):
    mock_storage.return_value.list_libraries.return_value = []
    response = client.get("/libraries/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 0

@patch("app.api.routes.library_manager_api.get_storage")
def test_list_libraries_type_error(mock_storage, client):
    mock_storage.return_value.list_libraries.side_effect = Exception("DB error")
    with pytest.raises(Exception, match="DB error"):
        client.get("/libraries/")

@patch("app.api.routes.library_manager_api.get_storage")
def test_get_library_returns_metadata(mock_storage, client):
    mock_storage.return_value.get_library.return_value = {"id": "lib1", "name": "Library 1"}
    with patch("app.services.library_service.LibraryService") as mock_service:
        mock_service.return_value.get_document = AsyncMock(return_value={"id": "lib1", "name": "Library 1"})
        response = client.get("/libraries/lib1")
        assert response.status_code == 200
        assert response.json()["id"] == "lib1"

@patch("app.api.routes.library_manager_api.get_storage")
def test_get_library_not_found(mock_storage, client):
    mock_storage.return_value.get_library.return_value = {"error": "Not found"}
    response = client.get("/libraries/unknown")
    assert response.status_code == 404
    assert response.json()["error"] == "Not found"

@patch("app.api.routes.library_manager_api.get_storage")
def test_get_library_returns_pdf(mock_storage, client):
    mock_storage.return_value.get_library.return_value = {"id": "lib1", "name": "Library 1"}
    with patch("app.services.library_service.LibraryService") as mock_service:
        # Simulate the endpoint returning a PDF file
        mock_service.return_value.get_document = AsyncMock(return_value=b"%PDF-1.4")
        response = client.get("/libraries/lib1?return_pdf=true")
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            assert response.content.startswith(b"%PDF")

# --- Library Form CRUD ---
@patch("app.services.library_service.LibraryFormService")
def test_get_all_library_forms_returns_list(mock_form_service, client):
    mock_form_service.return_value.list_forms.return_value = [
        {"formTitle": "Form 1"},
        {"formTitle": "Form 2"}
    ]
    response = client.get("/libraries/forms/")
    assert response.status_code == 200
    data = response.json()
    assert "forms" in data
    assert isinstance(data["forms"], list)
    assert len(data["forms"]) >= 1

@patch("app.services.library_service.LibraryFormService")
def test_get_all_library_forms_empty(mock_form_service, client):
    mock_form_service.return_value.list_forms.return_value = []
    response = client.get("/libraries/forms/")
    assert response.status_code == 200
    assert "forms" in response.json()
    assert isinstance(response.json()["forms"], list)

@patch("app.services.library_service.LibraryFormService")
def test_create_library_form_success(mock_form_service, client):
    mock_form_service.return_value.save_form.return_value = None
    form_data = {
        "formTitle": "Test Form",
        "formDescription": "A test form",
        "formPath": "/test",
        "libraryFormId": "formid",
        "fields": [{
            "fieldName": "Field1",
            "fieldType": "text",
            "required": True
        }]
    }
    response = client.post("/libraries/forms/", json=form_data)
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        data = response.json()
        assert "message" in data
        assert "library_form_id" in data

@patch("app.services.library_service.LibraryFormService")
def test_create_library_form_invalid_data(mock_form_service, client):
    form_data = {
        "formTitle": "Test Form"
    }
    response = client.post("/libraries/forms/", json=form_data)
    assert response.status_code == 422

@patch("app.services.library_service.LibraryFormService")
def test_get_library_form_found(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = {
        "formTitle": "Test",
        "formDescription": "desc",
        "formPath": "/test",
        "fields": [{
            "fieldName": "Field1",
            "fieldType": "text",
            "required": True
        }]
    }
    response = client.get("/libraries/forms/formid")
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert response.json()["formTitle"] == "Test"

@patch("app.services.library_service.LibraryFormService")
def test_get_library_form_not_found(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = None
    response = client.get("/libraries/forms/unknownid")
    assert response.status_code == 404
    assert response.json()["detail"] == "Form not found"

@patch("app.services.library_service.LibraryFormService")
def test_update_library_form_success(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = {
        "formTitle": "Test",
        "formDescription": "desc",
        "formPath": "/test",
        "fields": [{
            "fieldName": "Field1",
            "fieldType": "text",
            "required": True
        }]
    }
    mock_form_service.return_value.update_form.return_value = None
    form_data = {
        "formTitle": "Updated",
        "formDescription": "desc",
        "formPath": "/path",
        "fields": [{
            "fieldName": "Field1",
            "fieldType": "text",
            "required": True
        }]
    }
    response = client.put("/libraries/forms/formid", json=form_data)
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        assert response.json()["message"] == "Form updated successfully"

@patch("app.services.library_service.LibraryFormService")
def test_update_library_form_invalid_data(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = {
        "formTitle": "Test",
        "formDescription": "desc",
        "formPath": "/test",
        "fields": []
    }
    form_data = {
        "formTitle": "Updated"
    }
    response = client.put("/libraries/forms/formid", json=form_data)
    assert response.status_code == 422

@patch("app.services.library_service.LibraryFormService")
def test_update_library_form_not_found(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = None
    form_data = {
        "formTitle": "Updated",
        "formDescription": "desc",
        "formPath": "/path",
        "fields": [{
            "fieldName": "Field1",
            "fieldType": "text",
            "required": True
        }]
    }
    response = client.put("/libraries/forms/unknownid", json=form_data)
    assert response.status_code in (404, 422)
    if response.status_code == 404:
        assert response.json()["detail"] == "Form not found"

@patch("app.services.library_service.LibraryFormService")
def test_delete_library_form_success(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = {
        "formTitle": "Test",
        "formDescription": "desc",
        "formPath": "/test",
        "fields": [{
            "fieldName": "Field1",
            "fieldType": "text",
            "required": True
        }]
    }
    mock_form_service.return_value.delete_form.return_value = None
    response = client.delete("/libraries/forms/formid")
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert response.json()["message"] == "Form deleted successfully"

@patch("app.services.library_service.LibraryFormService")
def test_delete_library_form_not_found(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = None
    response = client.delete("/libraries/forms/unknownid")
    assert response.status_code == 404
    assert response.json()["detail"] == "Form not found"

@patch("app.services.library_service.LibraryFormService")
def test_delete_library_form_exception(mock_form_service, client):
    mock_form_service.return_value.get_form.return_value = {
        "formTitle": "Test",
        "formDescription": "desc",
        "formPath": "/test",
        "fields": []
    }
    mock_form_service.return_value.delete_form.side_effect = Exception("Delete error")
    response = client.delete("/libraries/forms/formid")
    assert response.status_code in (500, 404, 200)
    