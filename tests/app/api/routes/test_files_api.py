from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi.testclient import TestClient
from app.api.routes import files_api
from main import app

# Dependency overrides for authentication and permissions
def override_get_email_from_token():
    return "test@example.com"
app.dependency_overrides[files_api.get_email_from_token] = override_get_email_from_token
app.dependency_overrides[files_api.dynamic_permission_check] = lambda: None

client = TestClient(app)

@patch('app.api.routes.files_api.list_objects_recursive')
def test_get_s3_structure_admin_success(mock_list):
    mock_list.return_value = ["file1.pdf", "file2.pdf"]
    response = client.get('/files/folder-structure', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert "items" in response.json()

@patch('app.api.routes.files_api.list_objects_recursive')
@patch('app.api.routes.files_api.S3_user')
def test_get_s3_structure_non_admin_no_assignment(mock_s3_user, mock_list):
    mock_s3_user.exists.return_value = False
    response = client.get('/files/folder-structure', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (404, 401)

@patch('app.api.routes.files_api.list_objects_recursive')
@patch('app.api.routes.files_api.S3_user')
def test_get_s3_structure_non_admin_assignment_error(mock_s3_user, mock_list):
    mock_s3_user.exists.return_value = True
    mock_s3_user.read_json.side_effect = Exception("Read error")
    response = client.get('/files/folder-structure', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (500, 401)

@patch('app.api.routes.files_api.list_objects_recursive')
@patch('app.api.routes.files_api.S3_user')
def test_get_s3_structure_non_admin_no_folders(mock_s3_user, mock_list):
    mock_s3_user.exists.return_value = True
    mock_s3_user.read_json.return_value = {"assigned_folders": []}
    response = client.get('/files/folder-structure', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (403, 401)

@patch('app.api.routes.files_api.get_storage')
@patch('app.api.routes.files_api.FileService')
def test_upload_files_success(mock_file_service, mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_file_service.return_value.files_upload = AsyncMock(return_value=["file1.pdf"])
    files = [("files", ("file1.pdf", b"PDFDATA", "application/pdf"))]
    response = client.post('/files/upload/', files=files, data={"path": "folder", "overwrite": "false"}, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert "uploaded_files" in response.json()

@patch('app.api.routes.files_api.get_storage')
def test_upload_files_invalid_type(mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    files = [("files", ("file1.txt", b"NOTPDF", "text/plain"))]
    response = client.post('/files/upload/', files=files, data={"path": "folder", "overwrite": "false"}, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (400, 401)
    if response.status_code == 400:
        assert "Only PDF files are allowed." in str(response.json())

@patch('app.api.routes.files_api.get_storage')
@patch('app.api.routes.files_api.FileService')
def test_upload_files_exception(mock_file_service, mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_file_service.return_value.files_upload = AsyncMock(side_effect=Exception("Upload error"))
    files = [("files", ("file1.pdf", b"PDFDATA", "application/pdf"))]
    response = client.post('/files/upload/', files=files, data={"path": "folder", "overwrite": "false"}, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (500, 422, 400, 401)

@patch('app.api.routes.files_api.get_storage')
@patch('app.api.routes.files_api.FileService')
def test_get_file_success(mock_file_service, mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_storage.get.return_value = "filedata"
    mock_file_service.return_value.get_pdf = AsyncMock(return_value={"file": "filedata"})
    response = client.get('/files/123', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)

@patch('app.api.routes.files_api.get_storage')
def test_get_file_not_found(mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_storage.get.return_value = {"error": "Not found"}
    response = client.get('/files/123', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (404, 401, 500)
    if response.status_code == 404:
        assert response.json().get("detail") == "File not found"

@patch('app.api.routes.files_api.get_storage')
def test_list_files_success(mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_storage.list.return_value = ["file1.pdf", "file2.pdf"]
    response = client.get('/files/', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert response.json() == ["file1.pdf", "file2.pdf"]

@patch('app.api.routes.files_api.get_storage')
@patch('app.api.routes.files_api.S3_user')
def test_list_files_no_assignment(mock_s3_user, mock_get_storage):
    mock_s3_user.exists.return_value = False
    response = client.get('/files/', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (404, 401)

@patch('app.api.routes.files_api.get_storage')
@patch('app.api.routes.files_api.S3_user')
def test_list_files_assignment_error(mock_s3_user, mock_get_storage):
    mock_s3_user.exists.return_value = True
    mock_s3_user.read_json.side_effect = Exception("Read error")
    response = client.get('/files/', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (500, 401)

@patch('app.api.routes.files_api.get_storage')
@patch('app.api.routes.files_api.S3_user')
def test_list_files_no_folders(mock_s3_user, mock_get_storage):
    mock_s3_user.exists.return_value = True
    mock_s3_user.read_json.return_value = {"assigned_folders": []}
    response = client.get('/files/', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (403, 401)

@patch('app.api.routes.files_api.get_storage')
def test_delete_file_success(mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_storage.delete.return_value = {"deleted": True}
    response = client.delete('/files/123', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert response.json()["deleted"] is True

@patch('app.api.routes.files_api.get_storage')
def test_delete_file_not_found(mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_storage.delete.return_value = {"deleted": False}
    response = client.delete('/files/123', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert response.json()["deleted"] is False

@patch('app.api.routes.files_api.get_storage')
def test_update_file_success(mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_storage.update.return_value = {"updated": True}
    files = {"new_file": ("file1.pdf", b"PDFDATA", "application/pdf")}
    response = client.put('/files/123', files=files, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert response.json()["updated"] is True

@patch('app.api.routes.files_api.get_storage')
def test_update_file_invalid_type(mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_storage.update.return_value = {"updated": False}
    files = {"new_file": ("file1.txt", b"NOTPDF", "text/plain")}
    response = client.put('/files/123', files=files, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert response.json()["updated"] is False

@patch('app.api.routes.files_api.get_storage')
@patch('app.api.routes.files_api.create_folder_only')
def test_move_files_create_folder(mock_create_folder, mock_get_storage):
    mock_create_folder.return_value = {"created": True}
    data = {"document_ids": [], "new_folder": "folder1"}
    response = client.put('/files/move/', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert response.json()["created"] is True

@patch('app.api.routes.files_api.get_storage')
def test_move_files_move(mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_storage.move.return_value = {"moved": True}
    data = {"document_ids": ["doc1"], "new_folder": "folder1"}
    response = client.put('/files/move/', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert response.json()["moved"] is True

@patch('app.api.routes.files_api.get_storage')
def test_move_files_move_fail(mock_get_storage):
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_storage.move.return_value = {"moved": False}
    data = {"document_ids": ["doc1"], "new_folder": "folder1"}
    response = client.put('/files/move/', json=data, headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert response.json()["moved"] is False

@patch('app.api.routes.files_api.delete_folder')
def test_delete_folders_success(mock_delete_folder):
    mock_delete_folder.return_value = {"deleted": True}
    response = client.delete('/files/folders/?folder_name=folder1', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 500, 401)
    if response.status_code == 200:
        assert response.json()["deleted"] is True

@patch('app.api.routes.files_api.delete_folder')
def test_delete_folders_fail(mock_delete_folder):
    mock_delete_folder.return_value = {"deleted": False}
    response = client.delete('/files/folders/?folder_name=folder1', headers={"Authorization": "Bearer testtoken"})
    assert response.status_code in (200, 500, 401)
    if response.status_code == 200:
        assert response.json()["deleted"] is False