import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from app.services.template_service import TemplateManager
from repositories.s3_repo import s3_client
from botocore.exceptions import ClientError

@pytest.fixture
def template_data():
    return {
        "templates": {
            "template1": {
                "fields": [{"name": "field1"}],
                "parties": [{"name": "party1"}],
                "document_ids": ["doc1"]
            }
        },
        "document_id": "meta123"
    }

@pytest.fixture
def field_mock():
    m = MagicMock()
    m.dict.return_value = {"name": "fieldX"}
    return m

@pytest.fixture
def party_mock():
    m = MagicMock()
    m.dict.return_value = {"name": "partyX"}
    return m

@patch.object(TemplateManager, "load_all_templates")
def test_load_templates(mock_load, template_data):
    mock_load.return_value = template_data["templates"]
    tm = TemplateManager(email="test@example.com", user_email="user@example.com")
    result = tm.load_all_templates(is_global=False)
    assert "template1" in result

def test_load_templates_empty():
    with patch.object(TemplateManager, "load_all_templates", return_value={}) as mock_load:
        tm = TemplateManager(email="test@example.com", user_email="user@example.com")
        result = tm.load_all_templates(is_global=False)
        assert result == {}

def test_load_templates_corrupted():
    with patch.object(TemplateManager, "load_all_templates", return_value={}) as mock_load:
        tm = TemplateManager(email="test@example.com", user_email="user@example.com")
        result = tm.load_all_templates(is_global=False)
        assert result == {}

@patch.object(TemplateManager, "load_template_by_name")
@patch.object(TemplateManager, "save_template")
def test_create_template_success(mock_save, mock_load, field_mock, party_mock):
    mock_load.return_value = None  # simulate no existing template
    tm = TemplateManager(email="test@example.com", user_email="user@example.com")
    class DummyCreate:
        document_id = "docid"
    result = tm.create_template(DummyCreate(), "template_new", [field_mock], [party_mock])
    assert result["message"] == "Template 'template_new' created."
    mock_save.assert_called_once()

@patch.object(TemplateManager, "load_template_by_name")
@patch.object(TemplateManager, "save_template")
def test_create_template_empty(mock_save, mock_load):
    mock_load.return_value = None
    tm = TemplateManager(email="test@example.com", user_email="user@example.com")
    class DummyCreate:
        document_id = "docid"
    result = tm.create_template(DummyCreate(), "empty_template", [], [])
    assert result["message"] == "Template 'empty_template' created."
    mock_save.assert_called_once()

@patch.object(TemplateManager, "load_template_by_name")
def test_create_template_exists(mock_load, field_mock, party_mock):
    mock_load.return_value = {"fields": [], "parties": []}
    tm = TemplateManager(email="test@example.com", user_email="user@example.com")
    class DummyCreate:
        document_id = "docid"
    with pytest.raises(HTTPException) as exc:
        tm.create_template(DummyCreate(), "template1", [field_mock], [party_mock])
    assert exc.value.status_code == 400
    assert "already exists" in exc.value.detail

@patch.object(TemplateManager, "load_template_by_name")
@patch.object(TemplateManager, "save_template")
def test_update_template_fields(mock_save, mock_load, field_mock, template_data):
    mock_load.return_value = template_data["templates"]["template1"]
    tm = TemplateManager(email="test@example.com", user_email="user@example.com")
    class DummyUpdate:
        document_id = None
    result = tm.update_template(DummyUpdate(), "template1", fields=[field_mock])
    assert result["message"] == "Template 'template1' updated."
    mock_save.assert_called_once()

@patch.object(TemplateManager, "load_template_by_name")
@patch.object(TemplateManager, "save_template")
def test_update_template(mock_save, mock_load, field_mock, party_mock, template_data):
    mock_load.return_value = template_data["templates"]["template1"]
    tm = TemplateManager(email="test@example.com", user_email="user@example.com")
    class DummyUpdate:
        document_id = None
    result = tm.update_template(
        DummyUpdate(),
        "template1",
        fields=[field_mock],
        parties=[party_mock]
    )
    assert result["message"] == "Template 'template1' updated."
    mock_save.assert_called_once()

@patch.object(TemplateManager, "load_template_by_name")
@patch.object(TemplateManager, "save_template", side_effect=Exception("save error"))
def test_create_template_save_error(mock_save, mock_load):
    mock_load.return_value = None
    tm = TemplateManager(email="test@example.com", user_email="user@example.com")
    class DummyCreate:
        document_id = "docid"
    with pytest.raises(Exception) as exc:
        tm.create_template(DummyCreate(), "fail_template", [], [])
    assert "save error" in str(exc.value)

@patch.object(TemplateManager, "load_template_by_name")
@patch.object(TemplateManager, "save_template")
def test_update_template_empty(mock_save, mock_load, template_data):
    mock_load.return_value = template_data["templates"]["template1"]
    tm = TemplateManager(email="test@example.com", user_email="user@example.com")
    class DummyUpdate:
        document_id = None
    result = tm.update_template(DummyUpdate(), "template1", fields=[], parties=[])
    updated = template_data["templates"]["template1"]
    assert updated["fields"] == []
    assert updated["parties"] == []
    assert result["message"] == "Template 'template1' updated."
    mock_save.assert_called_once()

@patch.object(TemplateManager, "load_template_by_name")
def test_get_template_corrupted(mock_load):
    mock_load.return_value = {"templates": {"template1": {}}}
    tm = TemplateManager(email="test@example.com", user_email="user@example.com")
    template = tm.get_template("template1")
    assert template is not None
    assert "fields" not in template or template["fields"] == []

def test_delete_template_corrupted():
    with patch.object(TemplateManager, "_get_template_key", return_value="somekey.json"):
        with patch.object(s3_client, "delete_object") as mock_delete:
            tm = TemplateManager(email="test@example.com", user_email="user@example.com")
            result = tm.delete_template("template1")
            assert result["message"] == "Template 'template1' deleted."