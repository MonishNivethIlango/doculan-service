from unittest.mock import patch
from fastapi.testclient import TestClient
from app.api.routes import contacts_api
from main import app
import uuid

# Dependency overrides for authentication and permissions
def override_get_email_from_token():
    return "test@example.com"
app.dependency_overrides[contacts_api.get_email_from_token] = override_get_email_from_token
app.dependency_overrides[contacts_api.dynamic_permission_check] = lambda: None

client = TestClient(app)

sample_address = {
    "street": "123 Main St",
    "city": "Metropolis",
    "state": "NY",
    "zip": "12345",
    "country": "USA"
}
sample_contact = {
    "name": "John Doe",
    "email": "john@example.com",
    "organization": "Acme Corp",
    "mobile": "1234567890",
    "address": sample_address
}

@patch('app.services.contact_service.ContactService.create_contact')
def test_create_contact_success(mock_create):
    mock_create.return_value = None
    response = client.post('/contacts/', json=sample_contact, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert "contact_id" in response.json()

@patch('app.services.contact_service.ContactService.create_contact')
def test_create_contact_validation_error(mock_create):
    bad_contact = sample_contact.copy()
    bad_contact.pop("email")
    response = client.post('/contacts/', json=bad_contact, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 422

@patch('app.services.contact_service.ContactService.get_contact')
def test_get_contact_success(mock_get):
    mock_get.return_value = sample_contact
    contact_id = str(uuid.uuid4())
    response = client.get(f'/contacts/{contact_id}', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json()["name"] == sample_contact["name"]

@patch('app.services.contact_service.ContactService.get_contact')
def test_get_contact_not_found(mock_get):
    mock_get.return_value = None
    contact_id = str(uuid.uuid4())
    response = client.get(f'/contacts/{contact_id}', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 404

@patch('app.services.contact_service.ContactService.get_all_contacts')
def test_get_all_contacts_success(mock_get_all):
    mock_get_all.return_value = [sample_contact]
    response = client.get('/contacts/', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert "contacts" in response.json()

@patch('app.services.contact_service.ContactService.get_all_contacts')
def test_get_all_contacts_empty(mock_get_all):
    mock_get_all.return_value = []
    response = client.get('/contacts/', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json()["contacts"] == []

@patch('app.services.contact_service.ContactService.get_contact')
@patch('app.services.contact_service.ContactService.update_contact')
def test_update_contact_success(mock_update, mock_get):
    mock_get.return_value = sample_contact
    mock_update.return_value = None
    contact_id = str(uuid.uuid4())
    response = client.put(f'/contacts/{contact_id}', json=sample_contact, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json()["message"] == "Contact updated successfully"

@patch('app.services.contact_service.ContactService.get_contact')
@patch('app.services.contact_service.ContactService.update_contact')
def test_update_contact_not_found(mock_update, mock_get):
    mock_get.return_value = None
    contact_id = str(uuid.uuid4())
    response = client.put(f'/contacts/{contact_id}', json=sample_contact, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 404

@patch('app.services.contact_service.ContactService.get_contact')
@patch('app.services.contact_service.ContactService.delete_contact')
def test_delete_contact_success(mock_delete, mock_get):
    mock_get.return_value = sample_contact
    mock_delete.return_value = None
    contact_id = str(uuid.uuid4())
    response = client.delete(f'/contacts/{contact_id}', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json()["message"] == "Contact deleted successfully"

@patch('app.services.contact_service.ContactService.get_contact')
@patch('app.services.contact_service.ContactService.delete_contact')
def test_delete_contact_not_found(mock_delete, mock_get):
    mock_get.return_value = None
    contact_id = str(uuid.uuid4())
    response = client.delete(f'/contacts/{contact_id}', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 404
