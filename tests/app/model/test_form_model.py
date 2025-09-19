import sys
from unittest.mock import MagicMock

# Patch the db before importing anything that uses it
sys.modules["auth_app.app.database.connection"] = MagicMock()

import pytest
from unittest.mock import patch, MagicMock as MM, ANY, AsyncMock
from fastapi import HTTPException
from app.model.form_model import FormModel
import json
from botocore.exceptions import ClientError

@pytest.fixture
def email():
    return "user@example.com"

@pytest.fixture
def form_id():
    return "form123"

@pytest.fixture
def form_data():
    return {
        "formTitle": "Sample Form",
        "fields": [
            {"id": "f1", "label": "Name", "required": True},
            {"id": "f2", "label": "Email", "required": False}
        ]
    }

@pytest.fixture
def party_email():
    return "party@example.com"

@pytest.fixture
def mock_get_object():
    with patch("app.model.form_model.s3_client.get_object") as mock:
        yield mock

@pytest.fixture
def mock_put_object():
    with patch("app.model.form_model.s3_client.put_object") as mock:
        yield mock

@pytest.fixture
def mock_delete_object():
    with patch("app.model.form_model.s3_client.delete_object") as mock:
        yield mock

def test_get_form_success(mock_get_object, email, form_id, form_data):
    mock_get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=json.dumps(form_data).encode("utf-8")))
    }
    result = FormModel.get_form(form_id, email)
    assert result == form_data

def test_get_form_not_found(mock_get_object, email, form_id):
    mock_get_object.side_effect = Exception("Not found")
    result = FormModel.get_form(form_id, email)
    assert result == {}

def test_save_form(mock_put_object, email, form_id, form_data):
    FormModel.save_form(form_id, form_data, email)
    mock_put_object.assert_called_once()

def test_update_form_success(mock_get_object, mock_put_object, email, form_id, form_data):
    mock_get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=json.dumps(form_data).encode("utf-8")))
    }
    FormModel.update_form(form_id, form_data, email)
    mock_put_object.assert_called_once()

def test_update_form_failure(mock_get_object, email, form_id):
    mock_get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=b"{}"))
    }
    with pytest.raises(KeyError):
        FormModel.update_form(form_id, {}, email)

def test_list_forms_success(email, form_id, form_data):
    with patch("app.model.form_model.s3_client.list_objects_v2") as mock_list, \
         patch.object(FormModel, "_get_forms_json") as mock_get_json:
        mock_list.return_value = {
            "Contents": [
                {"Key": f"{email}/forms/{form_id}.json"},
                {"Key": f"{email}/forms/forms.json"}  # should be skipped
            ]
        }
        mock_get_json.return_value = form_data
        result = FormModel.list_forms(email)
        assert result == [{"formId": form_id, **form_data}]

def test_list_forms_error(email):
    with patch("app.model.form_model.s3_client.list_objects_v2", side_effect=Exception("fail")):
        with pytest.raises(HTTPException):
            FormModel.list_forms(email)

def test_delete_form_success(mock_delete_object, email, form_id):
    FormModel.delete_form(form_id, email)
    mock_delete_object.assert_called_once_with(Bucket=ANY, Key=f"{email}/forms/{form_id}.json")

def test_delete_form_error(mock_delete_object, email, form_id):
    mock_delete_object.side_effect = Exception("fail")
    with pytest.raises(HTTPException):
        FormModel.delete_form(form_id, email)

def test_validate_form_values_missing_fields():
    form = {
        "fields": [
            {"id": "f1", "label": "Name", "required": True},
            {"id": "f2", "label": "Email", "required": False}
        ]
    }
    values = {"Email": "test@example.com"}  # Missing Name
    with pytest.raises(HTTPException) as exc:
        FormModel.validate_form_values(form, values)
    assert exc.value.status_code == 400
    assert "Missing required fields" in exc.value.detail

def test_validate_form_values_ok():
    form = {
        "fields": [
            {"id": "f1", "label": "Name", "required": True},
            {"id": "f2", "label": "Email", "required": False}
        ]
    }
    values = {"Name": "John"}
    FormModel.validate_form_values(form, values)  # Should not raise

def test_get_form_user_data_success(email, form_id):
    with patch("app.model.form_model.s3_client.get_object") as mock_get:
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps({"foo": "bar"}).encode("utf-8")))
        }
        result = FormModel.get_form_user_data(form_id, email)
        assert result == {"foo": "bar"}

def test_get_form_user_data_no_such_key(email, form_id):
    with patch("app.model.form_model.s3_client.get_object", side_effect=ClientError({"Error": {"Code": "NoSuchKey"}}, "get_object")):
        result = FormModel.get_form_user_data(form_id, email)
        assert result == {}

def test_get_form_user_data_error(email, form_id):
    with patch("app.model.form_model.s3_client.get_object", side_effect=Exception("fail")):
        with pytest.raises(HTTPException):
            FormModel.get_form_user_data(form_id, email)

def test_upload_submission_tracking_and_user_data(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object") as mock_get, \
         patch("app.model.form_model.s3_client.put_object") as mock_put:
        # Tracking get_object returns NoSuchKey first, then user_data returns NoSuchKey
        def get_object_side_effect(Bucket, Key):
            if "trackings.json" in Key:
                raise ClientError({"Error": {"Code": "NoSuchKey"}}, "get_object")
            elif "form_user_data.json" in Key:
                raise ClientError({"Error": {"Code": "NoSuchKey"}}, "get_object")
        mock_get.side_effect = get_object_side_effect
        result = FormModel.upload_submission(
            email, form_id, party_email, {"submitted": True}, {"1": "val"}
        )
        assert isinstance(result, dict)

def test_upload_submission_tracking_update_error(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object", side_effect=Exception("fail")), \
         patch("app.model.form_model.s3_client.put_object"):
        with pytest.raises(HTTPException):
            FormModel.upload_submission(email, form_id, party_email, {"submitted": True})

def test_upload_submission_user_data_update_error(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object") as mock_get, \
         patch("app.model.form_model.s3_client.put_object", side_effect=Exception("fail")):
        def get_object_side_effect(Bucket, Key):
            if "trackings.json" in Key:
                raise ClientError({"Error": {"Code": "NoSuchKey"}}, "get_object")
            elif "form_user_data.json" in Key:
                raise ClientError({"Error": {"Code": "NoSuchKey"}}, "get_object")
        mock_get.side_effect = get_object_side_effect
        with pytest.raises(HTTPException):
            FormModel.upload_submission(email, form_id, party_email, {"submitted": True}, {"1": "val"})

@pytest.mark.asyncio
async def test_upload_pdfs(email, form_id, party_email):
    with patch("app.model.form_model.AESCipher") as mock_cipher, \
         patch("app.model.form_model.s3_client.put_object") as mock_put, \
         patch("app.model.form_model.s3_client.get_object") as mock_get, \
         patch("app.model.form_model.EncryptionService.resolve_encryption_email", new_callable=AsyncMock) as mock_resolve_email, \
         patch("app.model.form_model.FormModel.get_form_party_name") as mock_party_name:
        mock_cipher.return_value.encrypt.return_value = b"encrypted"
        mock_get.side_effect = [Exception("NoSuchKey")]
        mock_resolve_email.return_value = "encryption@email"
        mock_party_name.return_value = "Party Name"
        pdf_bytes = b"pdfdata"
        result = await FormModel.upload_pdfs(email, form_id, party_email, pdf_bytes, "path", "Title")
        assert "pdf_key" in result and "metadata_key" in result

@pytest.mark.asyncio
async def test_get_pdfs(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object") as mock_get, \
         patch("app.model.form_model.AESCipher") as mock_cipher, \
         patch("app.model.form_model.EncryptionService.resolve_encryption_email", new_callable=AsyncMock) as mock_resolve_email:
        mock_get.return_value = {"Body": MagicMock(read=MagicMock(return_value=b"encrypted"))}
        mock_cipher.return_value.decrypt.return_value = b"decrypted"
        mock_resolve_email.return_value = "encryption@email"
        form = {"formPath": "path", "formTitle": "Title"}
        result = await FormModel.get_pdfs(email, form_id, party_email, form)
        assert result == b"decrypted"

def test_send_form(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object", side_effect=ClientError({"Error": {"Code": "NoSuchKey"}}, "get_object")), \
         patch("app.model.form_model.s3_client.put_object"):
        FormModel.send_form(email, form_id, party_email, {"fields": [], "email_responses": []})

def test_send_form_error(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object", side_effect=Exception("fail")), \
         patch("app.model.form_model.s3_client.put_object"):
        with pytest.raises(HTTPException):
            FormModel.send_form(email, form_id, party_email, {"fields": [], "email_responses": []})

def test_cancel_form_party(email, form_id, party_email):
    data = MagicMock()
    data.client_info = {}
    data.holder = {}
    with patch("app.model.form_model.s3_client.get_object") as mock_get, \
         patch("app.model.form_model.s3_client.put_object"):
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps({party_email: {"status": {}}}).encode("utf-8")))
        }
        result = FormModel.cancel_form_party(email, data, form_id, party_email)
        assert "msg" in result

def test_cancel_form_party_not_found(email, form_id, party_email):
    data = MagicMock()
    data.client_info = {}
    data.holder = {}
    with patch("app.model.form_model.s3_client.get_object") as mock_get:
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps({}).encode("utf-8")))
        }
        with pytest.raises(HTTPException):
            FormModel.cancel_form_party(email, data, form_id, party_email)

def test_get_form_party_name(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object") as mock_get:
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps({party_email: {"name": "Party Name"}}).encode("utf-8")))
        }
        result = FormModel.get_form_party_name(email, form_id, party_email)
        assert result == "Party Name"

def test_get_form_party_name_not_found(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object") as mock_get:
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps({}).encode("utf-8")))
        }
        with pytest.raises(HTTPException):
            FormModel.get_form_party_name(email, form_id, party_email)

def test_get_form_track(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object") as mock_get:
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps([{"id": party_email}]).encode("utf-8")))
        }
        result = FormModel.get_form_track(email, form_id, party_email)
        assert isinstance(result, list)

def test_update_tracking_status_by_party(email, form_id, party_email):
    from fastapi import Request
    class DummyRequest:
        client = type("client", (), {"host": "127.0.0.1"})()
        headers = {"user-agent": "test-agent"}
    with patch("app.model.form_model.s3_client.get_object") as mock_get, \
         patch("app.model.form_model.s3_client.put_object"):
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps([{"id": party_email}]).encode("utf-8")))
        }
        result = FormModel.update_tracking_status_by_party(email, form_id, party_email, "NEW", DummyRequest())
        assert result["success"]

def test_update_tracking_status_by_party_not_found(email, form_id):
    from fastapi import Request
    class DummyRequest:
        client = type("client", (), {"host": "127.0.0.1"})()
        headers = {"user-agent": "test-agent"}
    with patch("app.model.form_model.s3_client.get_object") as mock_get:
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps([]).encode("utf-8")))
        }
        with pytest.raises(HTTPException):
            FormModel.update_tracking_status_by_party(email, form_id, "notfound", "NEW", DummyRequest())

def test_update_party_status_by_tracking(email, form_id, party_email):
    with patch("app.model.form_model.s3_client.get_object") as mock_get, \
         patch("app.model.form_model.s3_client.put_object"):
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps([{"id": party_email}]).encode("utf-8")))
        }
        FormModel.update_party_status_by_tracking(email, form_id, party_email, "NEW")

def test_update_party_status_by_tracking_not_found(email, form_id):
    with patch("app.model.form_model.s3_client.get_object") as mock_get:
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps([]).encode("utf-8")))
        }
        with pytest.raises(HTTPException):
            FormModel.update_party_status_by_tracking(email, form_id, "notfound", "NEW")

def test_update_tracking_status_all_parties(email, form_id):
    with patch("app.model.form_model.s3_client.list_objects_v2") as mock_list, \
         patch("app.model.form_model.s3_client.get_object") as mock_get, \
         patch("app.model.form_model.s3_client.put_object"):
        mock_list.return_value = {"Contents": [{"Key": "key"}]}
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps([{"id": "id"}]).encode("utf-8")))
        }
        FormModel.update_tracking_status_all_parties(email, form_id, "NEW")

@pytest.mark.asyncio
async def test_resend_form_s3_tracking(email, form_id):
    with patch("app.model.form_model.s3_client.list_objects_v2") as mock_list, \
         patch("app.model.form_model.s3_client.get_object") as mock_get:
        mock_list.return_value = {"Contents": [{"Key": f"{email}/metadata/forms/{form_id}/tracking.json"}]}
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps({"foo": "bar"}).encode("utf-8")))
        }
        result = await FormModel.resend_form_s3_tracking(email, form_id)
        assert isinstance(result, dict)

def test_get_all_tracking_id(email, form_id):
    with patch("app.model.form_model.s3_client.list_objects_v2") as mock_list:
        mock_list.return_value = {"Contents": [{"Key": f"{email}/metadata/forms/{form_id}/tracking.json"}]}
        result = FormModel.get_all_tracking_id(email, form_id)
        assert isinstance(result, list)

def test_get_all_trackings(email, form_id):
    with patch("app.model.form_model.s3_client.list_objects_v2") as mock_list, \
         patch("app.model.form_model.s3_client.get_object") as mock_get:
        mock_list.return_value = {"Contents": [{"Key": f"{email}/metadata/forms/{form_id}/tracking.json"}]}
        mock_get.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps({"foo": "bar"}).encode("utf-8")))
        }
        result = FormModel.get_all_trackings(email, form_id)
        assert isinstance(result, dict)