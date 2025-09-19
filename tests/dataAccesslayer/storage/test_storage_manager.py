import pytest
from unittest.mock import MagicMock

from DataAccessLayer.storage.storage_manager import StorageManager


@pytest.fixture
def mock_strategy():
    return MagicMock()


@pytest.fixture
def storage_manager(mock_strategy):
    return StorageManager(strategy=mock_strategy)


def test_upload(storage_manager, mock_strategy):
    storage_manager.upload("user@example.com", "doc123", "fake_file.pdf", "folder/", overwrite=True)
    mock_strategy.upload_file.assert_called_once_with("user@example.com", "doc123", "fake_file.pdf", "folder/", True)


def test_get(storage_manager, mock_strategy):
    storage_manager.get("user@example.com", "doc123", return_pdf=True)
    mock_strategy.get_file.assert_called_once_with("user@example.com", "doc123", True)


def test_delete(storage_manager, mock_strategy):
    storage_manager.delete("user@example.com", "doc123")
    mock_strategy.delete_file.assert_called_once_with("user@example.com", "doc123")


def test_update(storage_manager, mock_strategy):
    storage_manager.update("user@example.com", "doc123", "updated_file.pdf")
    mock_strategy.update_file.assert_called_once_with("user@example.com", "doc123", "updated_file.pdf")


def test_list(storage_manager, mock_strategy):
    storage_manager.list("user@example.com")
    mock_strategy.list_files.assert_called_once_with("user@example.com")


def test_move(storage_manager, mock_strategy):
    document_ids = ["doc1", "doc2"]
    storage_manager.move("user@example.com", document_ids, "archive/")
    mock_strategy.move_file.assert_called_once_with("user@example.com", document_ids, "archive/")
