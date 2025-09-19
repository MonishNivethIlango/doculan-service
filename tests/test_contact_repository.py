import pytest
from unittest.mock import patch, MagicMock
from repositories.contact_repository import ContactRepository

@pytest.fixture
def contact_id():
    return "contact123"

@pytest.fixture
def contact_data():
    return {"name": "John Doe", "phone": "1234567890"}

@pytest.fixture
def updated_data():
    return {"name": "Jane Doe", "phone": "0987654321"}

@pytest.fixture
def email():
    return "test@example.com"

def test_create_contact(contact_id, contact_data, email):
    with patch("app.model.contact_model.ContactModel.save_contact", return_value="created") as mock_save:
        result = ContactRepository.create_contact(contact_id, contact_data, email)
        mock_save.assert_called_once_with(contact_id, contact_data, email)
        assert result == "created"

def test_get_all_contacts(email):
    with patch("app.model.contact_model.ContactModel.list_contacts", return_value=[{"id": 1}]) as mock_list:
        result = ContactRepository.get_all_contacts(email)
        mock_list.assert_called_once_with(email)
        assert result == [{"id": 1}]

def test_read_contact(contact_id, email):
    with patch("app.model.contact_model.ContactModel.get_contact", return_value={"id": 1}) as mock_get:
        result = ContactRepository.read_contact(contact_id, email)
        mock_get.assert_called_once_with(contact_id, email)
        assert result == {"id": 1}

def test_update_contact(contact_id, updated_data, email):
    with patch("app.model.contact_model.ContactModel.update_contact", return_value="updated") as mock_update:
        result = ContactRepository.update_contact(contact_id, updated_data, email)
        mock_update.assert_called_once_with(contact_id, updated_data, email)
        assert result == "updated"

def test_delete_contact(contact_id, email):
    with patch("app.model.contact_model.ContactModel.delete_contact", return_value="deleted") as mock_delete:
        result = ContactRepository.delete_contact(contact_id, email)
        mock_delete.assert_called_once_with(contact_id, email)
        assert result == "deleted"
