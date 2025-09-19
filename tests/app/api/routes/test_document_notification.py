
import sys
from unittest.mock import patch, MagicMock
import pytest

# Patch the DB connection and any side-effectful imports before importing the API module
mock_db = MagicMock()
sys.modules['auth_app.app.database.connection'] = MagicMock(db=mock_db, get_document_send_count_for_user_this_month=MagicMock(), get_document_send_count_for_org_this_month=MagicMock())

from fastapi.testclient import TestClient
from app.api.routes import document_notification
from main import app

# Dependency overrides for authentication and permissions
def override_get_email_from_token():
    return "test@example.com"
app.dependency_overrides[document_notification.get_email_from_token] = override_get_email_from_token
app.dependency_overrides[document_notification.dynamic_permission_check] = lambda: None

client = TestClient(app)

@patch('app.api.routes.document_notification.s3_download_json')
@patch('app.api.routes.document_notification.s3_list_objects')
def test_get_all_notifications_success(mock_list, mock_download):
    mock_list.return_value = ["test@example.com/notifications/1.json", "test@example.com/notifications/2.json"]
    def download_side_effect(key):
        if key.endswith("1.json"):
            return {"id": "1", "msg": "A"}
        elif key.endswith("2.json"):
            return {"id": "2", "msg": "B"}
        return None
    mock_download.side_effect = download_side_effect
    response = client.get('/notifications', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["id"] == "1"

@patch('app.api.routes.document_notification.s3_list_objects')
def test_get_all_notifications_empty(mock_list):
    mock_list.return_value = []
    response = client.get('/notifications', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json() == []

@patch('app.api.routes.document_notification.s3_delete_object')
def test_delete_notification_success(mock_delete):
    mock_delete.return_value = None
    response = client.delete('/notifications/123', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json()["message"] == "Notification deleted"

@patch('app.api.routes.document_notification.s3_download_json')
def test_get_notification_success(mock_download):
    def download_side_effect(key):
        if key.endswith("123.json"):
            return {"id": "123", "msg": "A"}
        return None
    mock_download.side_effect = download_side_effect
    response = client.get('/notifications/123', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert response.json()["id"] == "123"

@patch('app.api.routes.document_notification.s3_download_json')
def test_get_notification_not_found(mock_download):
    mock_download.return_value = None
    response = client.get('/notifications/123', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 404
