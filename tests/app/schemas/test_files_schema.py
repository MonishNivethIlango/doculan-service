import pytest
from pydantic import ValidationError
from app.schemas.files_schema import MoveFilesRequest

def test_move_files_request_valid():
    req = MoveFilesRequest(document_ids=['doc1', 'doc2'], new_folder='folderA')
    assert req.document_ids == ['doc1', 'doc2']
    assert req.new_folder == 'folderA'

def test_move_files_request_default_document_ids():
    req = MoveFilesRequest(new_folder='folderB')
    assert req.document_ids == []
    assert req.new_folder == 'folderB'

def test_move_files_request_invalid():
    with pytest.raises(ValidationError):
        MoveFilesRequest()
