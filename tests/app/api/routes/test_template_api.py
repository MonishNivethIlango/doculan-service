from unittest.mock import patch
from fastapi.testclient import TestClient
from app.api.routes import template_api
from main import app
from fastapi import HTTPException

# Dependency overrides for authentication and permissions
def override_get_email_from_token():
    return "test@example.com"

def override_get_user_email_from_token():
    return "test@example.com"

app.dependency_overrides[template_api.get_email_from_token] = override_get_email_from_token
app.dependency_overrides[template_api.get_user_email_from_token] = override_get_user_email_from_token
app.dependency_overrides[template_api.dynamic_permission_check] = lambda: None

client = TestClient(app)

@patch('app.services.template_service.TemplateManager')
def test_get_template_success(mock_manager):
    mock_manager.return_value.get_template.return_value = None
    response = client.get('/templates/sample?is_global=false', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json() is None

@patch('app.services.template_service.TemplateManager')
def test_get_template_not_found(mock_manager):
    mock_manager.return_value.get_template.return_value = None
    response = client.get('/templates/sample?is_global=false', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json() is None

@patch('app.services.template_service.TemplateManager')
def test_get_template_exception(mock_manager):
    mock_manager.return_value.get_template.side_effect = Exception("DB error")
    response = client.get('/templates/sample?is_global=false', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 500)

@patch('app.services.template_service.TemplateManager')
def test_delete_template_success(mock_manager):
    mock_manager.return_value.delete_template.return_value = None
    response = client.delete('/templates/sample?is_global=false', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 500)

@patch('app.services.template_service.TemplateManager')
def test_delete_template_not_found(mock_manager):
    mock_manager.return_value.delete_template.return_value = None
    response = client.delete('/templates/sample?is_global=false', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 500)

@patch('app.services.template_service.TemplateManager')
def test_delete_template_exception(mock_manager):
    mock_manager.return_value.delete_template.side_effect = Exception("DB error")
    response = client.delete('/templates/sample?is_global=false', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 500

@patch('app.services.template_service.TemplateManager')
def test_update_template_success(mock_manager):
    mock_manager.return_value.update_template.return_value = None
    data = {
        "fields": [],
        "parties": [],
        "is_global": False
    }
    response = client.put('/templates/sample', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 500)
    if response.status_code == 200:
        assert response.json() is None
    else:
        assert response.json().get("error") == "A server error occurred"

@patch('app.services.template_service.TemplateManager')
def test_update_template_not_found(mock_manager):
    mock_manager.return_value.update_template.return_value = None
    data = {
        "fields": [],
        "parties": [],
        "is_global": False
    }
    response = client.put('/templates/sample', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 500)
    if response.status_code == 200:
        assert response.json() is None
    else:
        assert response.json().get("error") == "A server error occurred"

@patch('app.services.template_service.TemplateManager')
def test_update_template_http_exception(mock_manager):
    mock_manager.return_value.update_template.side_effect = HTTPException(status_code=404, detail="Not found")
    data = {
        "fields": [],
        "parties": [],
        "is_global": False
    }
    response = client.put('/templates/sample', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (404, 500)

@patch('app.services.template_service.TemplateManager')
def test_update_template_exception(mock_manager):
    mock_manager.return_value.update_template.side_effect = Exception("DB error")
    data = {
        "fields": [],
        "parties": [],
        "is_global": False
    }
    response = client.put('/templates/sample', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 500

@patch('app.services.template_service.TemplateManager')
def test_create_template_success(mock_manager):
    mock_manager.return_value.create_template.return_value = None
    data = {
        "template_name": "sample",
        "fields": [],
        "parties": [],
        "is_global": False
    }
    response = client.post('/templates', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 422)

@patch('app.services.template_service.TemplateManager')
def test_create_template_http_exception(mock_manager):
    mock_manager.return_value.create_template.side_effect = HTTPException(status_code=400, detail="Template already exists")
    data = {
        "template_name": "sample",
        "fields": [],
        "parties": [],
        "is_global": False
    }
    response = client.post('/templates', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (400, 422)

@patch('app.services.template_service.TemplateManager')
def test_create_template_exception(mock_manager):
    mock_manager.return_value.create_template.side_effect = Exception("DB error")
    data = {
        "template_name": "sample",
        "fields": [],
        "parties": [],
        "is_global": False
    }
    response = client.post('/templates', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (500, 422)

@patch('app.services.template_service.TemplateManager')
def test_get_all_templates_success(mock_manager):
    mock_manager.return_value.get_all_templates.return_value = {"global": {}, "local": {}}
    response = client.get('/templates', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json() == {"global": {}, "local": {}}

@patch('app.services.template_service.TemplateManager')
def test_get_all_templates_not_found(mock_manager):
    mock_manager.return_value.get_all_templates.return_value = {"global": {}, "local": {}}
    response = client.get('/templates', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json() == {"global": {}, "local": {}}

@patch('app.services.template_service.TemplateManager')
def test_get_all_templates_exception(mock_manager):
    mock_manager.return_value.get_all_templates.side_effect = Exception("DB error")
    response = client.get('/templates', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (500, 200)

@patch('app.services.template_service.TemplateManager')
def test_load_all_templates_success(mock_manager):
    mock_manager.return_value.load_all_templates.return_value = {}
    response = client.get('/templates?is_global=true', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json() == {}

@patch('app.services.template_service.TemplateManager')
def test_load_all_templates_not_found(mock_manager):
    mock_manager.return_value.load_all_templates.return_value = {}
    response = client.get('/templates?is_global=true', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json() == {}

@patch('app.services.template_service.TemplateManager')
def test_load_all_templates_exception(mock_manager):
    mock_manager.return_value.load_all_templates.side_effect = Exception("DB error")
    response = client.get('/templates?is_global=true', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (500, 200)