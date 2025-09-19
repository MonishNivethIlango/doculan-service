import pytest
from DataAccessLayer.storage.base import StorageStrategy

# Test that StorageStrategy cannot be instantiated directly
def test_storage_strategy_cannot_instantiate():
    with pytest.raises(TypeError):
        StorageStrategy()

# Test that a subclass must implement all abstract methods
class IncompleteStorage(StorageStrategy):
    def upload_file(self, email, document_id, new_file, path_prefix="", overwrite=False): pass
    def get_file(self, email, document_id, return_pdf=False): pass
    def delete_file(self, email, document_id): pass
    def update_file(self, email, document_id, new_file): pass
    def list_files(self, email): pass
    # move_file is missing

def test_incomplete_storage_strategy():
    with pytest.raises(TypeError):
        IncompleteStorage()

# Test that a complete subclass can be instantiated
class CompleteStorage(StorageStrategy):
    def upload_file(self, email, document_id, new_file, path_prefix="", overwrite=False): return True
    def get_file(self, email, document_id, return_pdf=False): return True
    def delete_file(self, email, document_id): return True
    def update_file(self, email, document_id, new_file): return True
    def list_files(self, email): return []
    def move_file(self, email, document_ids, new_folder): return True

def test_complete_storage_strategy():
    s = CompleteStorage()
    assert s.upload_file('a', 'b', 'c') is True
    assert s.get_file('a', 'b') is True
    assert s.delete_file('a', 'b') is True
    assert s.update_file('a', 'b', 'c') is True
    assert s.list_files('a') == []
    assert s.move_file('a', ['b'], 'folder') is True
