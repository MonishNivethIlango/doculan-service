import pytest
from unittest.mock import patch, MagicMock
from app.services import contact_service

# Test create_contact
@patch("app.services.contact_service.ContactRepository")
def test_create_contact(mock_repo):
    mock_repo.create_contact.return_value = {"id": "1", "name": "Test"}
    result = contact_service.ContactService.create_contact("1", {"name": "Test"}, "user@example.com")
    assert result == {"id": "1", "name": "Test"}
    mock_repo.create_contact.assert_called_once_with("1", {"name": "Test"}, "user@example.com")

# Test get_contact
@patch("app.services.contact_service.ContactRepository")
def test_get_contact(mock_repo):
    mock_repo.read_contact.return_value = {"id": "1", "name": "Test"}
    result = contact_service.ContactService.get_contact("1", "user@example.com")
    assert result == {"id": "1", "name": "Test"}
    mock_repo.read_contact.assert_called_once_with("1", "user@example.com")

# Test get_all_contacts
@patch("app.services.contact_service.ContactRepository")
def test_get_all_contacts(mock_repo):
    mock_repo.get_all_contacts.return_value = [{"id": "1", "name": "Test"}]
    result = contact_service.ContactService.get_all_contacts("user@example.com")
    assert result == [{"id": "1", "name": "Test"}]
    mock_repo.get_all_contacts.assert_called_once_with("user@example.com")

# Test update_contact
@patch("app.services.contact_service.ContactRepository")
def test_update_contact(mock_repo):
    mock_repo.update_contact.return_value = {"id": "1", "name": "Updated"}
    result = contact_service.ContactService.update_contact("1", {"name": "Updated"}, "user@example.com")
    assert result == {"id": "1", "name": "Updated"}
    mock_repo.update_contact.assert_called_once_with("1", {"name": "Updated"}, "user@example.com")

# Test delete_contact
@patch("app.services.contact_service.ContactRepository")
def test_delete_contact(mock_repo):
    mock_repo.delete_contact.return_value = True
    result = contact_service.ContactService.delete_contact("1", "user@example.com")
    assert result is True
    mock_repo.delete_contact.assert_called_once_with("1", "user@example.com")
