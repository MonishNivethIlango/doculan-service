import pytest
from unittest.mock import patch, MagicMock, call
from botocore.exceptions import ClientError
from fastapi import HTTPException
import repositories.s3_repo as s3_repo
import json
from datetime import datetime, timezone
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException

@pytest.fixture
def mock_config():
    with patch('repositories.s3_repo.config') as mock_cfg:
        mock_cfg.S3_BUCKET = 'test-bucket'
        mock_cfg.KMS_KEY_ID = 'test-kms-key'
        mock_cfg.STORAGE_TYPE = 's3'
        yield mock_cfg

@pytest.fixture
def mock_s3_client():
    with patch('repositories.s3_repo.s3_client') as mock_client:
        yield mock_client

@pytest.fixture
def mock_logger():
    with patch('repositories.s3_repo.logger') as mock_log:
        yield mock_log

def test_generate_summary_from_trackings():
    trackings = {
        't1': {'status': 'completed'},
        't2': {'status': 'in_progress'},
        't3': {'status': 'completed'},
        't4': {},
    }
    result = s3_repo.generate_summary_from_trackings(trackings)
    assert result['total_documents'] == 1
    assert result['total_trackings'] == 4
    assert result['status_counts']['completed'] == 2
    assert result['status_counts']['in_progress'] == 1
    assert result['status_counts']['unknown'] == 1

def test_load_tracking_metadata_success(mock_s3_client, mock_config, mock_logger):
    mock_obj = {'Body': MagicMock()}
    mock_obj['Body'].read.return_value = b'{"foo": "bar"}'
    mock_s3_client.get_object.return_value = mock_obj
    result = s3_repo.load_tracking_metadata('user', 'doc1', 'track1')
    assert result == {'foo': 'bar'}
    mock_s3_client.get_object.assert_called_once()



def test_load_tracking_metadata_no_such_key(mock_s3_client, mock_config, mock_logger):
    # Patch s3_client.exceptions.NoSuchKey to ClientError to match the try-except in s3_repo.py
    s3_repo.s3_client.exceptions = type('MockExceptions', (), {
        'NoSuchKey': ClientError
    })

    # Raise ClientError when get_object is called
    error_response = {
        'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist.'}
    }
    operation_name = 'GetObject'
    mock_s3_client.get_object.side_effect = ClientError(error_response, operation_name)

    # Now run the actual function
    with pytest.raises(HTTPException) as exc:
        s3_repo.load_tracking_metadata('user', 'doc1', 'track1')

    assert exc.value.status_code == 404
    assert exc.value.detail == "Tracking metadata not found"

def test_load_tracking_metadata_other_error(mock_s3_client, mock_config, mock_logger):
    # Patch s3_client.exceptions.NoSuchKey so the except block doesn't crash
    s3_repo.s3_client.exceptions = type('MockExceptions', (), {
        'NoSuchKey': ClientError
    })

    # Simulate an unexpected exception from S3
    mock_s3_client.get_object.side_effect = Exception("fail")

    with pytest.raises(HTTPException) as exc:
        s3_repo.load_tracking_metadata('user', 'doc1', 'track1')

    assert exc.value.status_code == 500
    assert exc.value.detail == "Error loading tracking metadata"

def test_save_tracking_metadata_success(mock_s3_client, mock_config, mock_logger):
    # Patch NoSuchKey exception
    s3_repo.s3_client.exceptions = type("MockExceptions", (), {
        "NoSuchKey": ClientError
    })

    # Simulate metadata not existing
    error_response = {
        'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist.'}
    }
    mock_s3_client.get_object.side_effect = ClientError(error_response, 'GetObject')

    s3_repo.save_tracking_metadata('user', 'doc1', 'track1', {'tracking_status': {'status': 'completed'}})
    assert mock_s3_client.put_object.call_count == 2


def test_save_tracking_metadata_existing_doc(mock_s3_client, mock_config, mock_logger):
    # Simulate existing doc metadata
    doc_data = {'document_id': 'doc1', 'trackings': {}, 'defaults': {}}
    mock_obj = {'Body': MagicMock()}
    mock_obj['Body'].read.return_value = json.dumps(doc_data).encode()
    mock_s3_client.get_object.return_value = mock_obj

    s3_repo.save_tracking_metadata('user', 'doc1', 'track1', {'tracking_status': {'status': 'completed'}})
    assert mock_s3_client.put_object.call_count == 2


def test_save_tracking_metadata_load_error(mock_s3_client, mock_config, mock_logger):
    mock_s3_client.get_object.side_effect = Exception('fail')
    with pytest.raises(HTTPException):
        s3_repo.save_tracking_metadata('user', 'doc1', 'track1', {'tracking_status': {'status': 'completed'}})


def test_save_tracking_metadata_save_error(mock_s3_client, mock_config, mock_logger):
    mock_s3_client.put_object.side_effect = Exception('fail')
    with pytest.raises(HTTPException):
        s3_repo.save_tracking_metadata('user', 'doc1', 'track1', {'tracking_status': {'status': 'completed'}})


def test_format_datetime_utc_valid():
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    dt_str = dt.isoformat()
    result = s3_repo.format_datetime_utc(dt_str)
    assert result.startswith('2024-01-01T12:00:00')


def test_format_datetime_utc_invalid():
    result = s3_repo.format_datetime_utc('not-a-date')
    assert result == 'not-a-date'


def test_get_all_document_statuses_flat(mock_s3_client, mock_config, mock_logger):
    mock_s3_client.list_objects_v2.return_value = {
        'Contents': [{'Key': 'user/metadata/tracking/doc1/track1.json'}]
    }
    mock_obj = {'Body': MagicMock()}
    tracking_data = {
        'document_id': 'doc1',
        'tracking_id': 'track1',
        'tracking_status': {'status': 'completed', 'dateTime': '2024-01-01T00:00:00Z'},
        'parties': ['p1']
    }
    mock_obj['Body'].read.return_value = json.dumps(tracking_data).encode()
    mock_s3_client.get_object.return_value = mock_obj

    result = s3_repo.get_all_document_statuses_flat('user')
    assert 'documents' in result
    assert result['documents'][0]['status'] == 'completed'


def test_get_all_document_statuses_flat_error(mock_s3_client, mock_config, mock_logger):
    mock_s3_client.get_object.side_effect = Exception('fail')
    mock_s3_client.list_objects_v2.return_value = {
        'Contents': [{'Key': 'user/metadata/tracking/doc1/track1.json'}]
    }

    result = s3_repo.get_all_document_statuses_flat('user')
    assert result['documents'] == []


def test_load_document_metadata_success(mock_s3_client, mock_config, mock_logger):
    mock_obj = {'Body': MagicMock()}
    mock_obj['Body'].read.return_value = b'{"foo": "bar"}'
    mock_s3_client.get_object.return_value = mock_obj

    result = s3_repo.load_document_metadata('user', 'doc1')
    assert result == {'foo': 'bar'}


def test_load_document_metadata_no_such_key(mock_s3_client, mock_config, mock_logger):
    # Patch NoSuchKey exception to avoid TypeError
    s3_repo.s3_client.exceptions = type("MockExceptions", (), {
        "NoSuchKey": ClientError
    })

    error_response = {
        'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist.'}
    }
    mock_s3_client.get_object.side_effect = ClientError(error_response, 'GetObject')

    with pytest.raises(HTTPException) as exc:
        s3_repo.load_document_metadata('user', 'doc1')

    assert exc.value.status_code == 404
    assert "document id not found" in str(exc.value.detail).lower()


def test_load_document_metadata_other_error(mock_s3_client, mock_config, mock_logger):
    # Patch NoSuchKey to avoid TypeError during catch
    s3_repo.s3_client.exceptions = type("MockExceptions", (), {
        "NoSuchKey": ClientError
    })

    # Simulate unexpected exception
    mock_s3_client.get_object.side_effect = Exception("fail")

    with pytest.raises(HTTPException) as exc:
        s3_repo.load_document_metadata('user', 'doc1')

    assert exc.value.status_code == 500
    assert "error loading document metadata" in str(exc.value.detail).lower()

    @pytest.fixture
    def mock_config():
        with patch('repositories.s3_repo.config') as mock_cfg:
            mock_cfg.S3_BUCKET = 'test-bucket'
            mock_cfg.KMS_KEY_ID = 'test-kms-key'
            yield mock_cfg

    @pytest.fixture
    def mock_s3_client():
        with patch('repositories.s3_repo.s3_client') as mock_client:
            yield mock_client

    @pytest.fixture
    def mock_logger():
        with patch('repositories.s3_repo.logger') as mock_log:
            yield mock_log

    def test_s3_download_string_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"hello"
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.s3_download_string("foo/bar.json")
        assert result == "hello"

    def test_s3_download_string_error(mock_s3_client, mock_config):
        mock_s3_client.get_object.side_effect = Exception("fail")
        with pytest.raises(Exception):
            s3_repo.s3_download_string("foo/bar.json")

    def test_s3_download_bytes_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"bytes"
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.s3_download_bytes("foo/bar.json")
        assert result == b"bytes"

    def test_s3_download_bytes_error(mock_s3_client, mock_config):
        mock_s3_client.get_object.side_effect = Exception("fail")
        with pytest.raises(Exception):
            s3_repo.s3_download_bytes("foo/bar.json")

    def test_s3_upload_bytes_success(mock_s3_client, mock_config):
        mock_s3_client.put_object.return_value = None
        assert s3_repo.s3_upload_bytes(b"bytes", "foo/bar.json", "application/json") is True

    def test_s3_upload_bytes_client_error(mock_s3_client, mock_config):
        mock_s3_client.put_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "PutObject")
        assert not s3_repo.s3_upload_bytes(b"bytes", "foo/bar.json", "application/json")

    def test_s3_upload_json_success(mock_s3_client, mock_config):
        s3_repo.s3_upload_json({"foo": "bar"}, "foo/bar.json")
        assert mock_s3_client.put_object.called

    def test_s3_upload_json_client_error(mock_s3_client, mock_config):
        mock_s3_client.put_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "PutObject")
        with pytest.raises(ClientError):
            s3_repo.s3_upload_json({"foo": "bar"}, "foo/bar.json")

    def test_s3_download_json_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"foo": "bar"}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.s3_download_json("foo/bar.json")
        assert result == {"foo": "bar"}

    def test_s3_download_json_no_such_key(mock_s3_client, mock_config):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        mock_s3_client.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        result = s3_repo.s3_download_json("foo/bar.json")
        assert result is None

    def test_s3_download_json_client_error(mock_s3_client, mock_config):
        mock_s3_client.get_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "GetObject")
        with pytest.raises(ClientError):
            s3_repo.s3_download_json("foo/bar.json")

    def test_s3_delete_object_success(mock_s3_client, mock_config):
        s3_repo.s3_delete_object("foo/bar.json")
        assert mock_s3_client.delete_object.called

    def test_s3_delete_objects_success(mock_s3_client, mock_config):
        s3_repo.s3_delete_objects("foo/bar.json")
        assert mock_s3_client.delete_object.called

    def test_s3_delete_objects_client_error(mock_s3_client, mock_config):
        mock_s3_client.delete_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "DeleteObject")
        with pytest.raises(ClientError):
            s3_repo.s3_delete_objects("foo/bar.json")

    def test_s3_list_objects_success(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "foo/bar.json"}, {"Key": "foo/baz.txt"}]
        }
        result = s3_repo.s3_list_objects("foo/")
        assert "foo/bar.json" in result

    def test_s3_list_objects_no_contents(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {}
        result = s3_repo.s3_list_objects("foo/")
        assert result == []

    def test_s3_list_object_success(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "foo/bar.json"}, {"Key": "foo/baz.txt"}]
        }
        result = s3_repo.s3_list_object("foo/")
        assert "foo/bar.json" in result

    def test__list_objects_success(mock_s3_client, mock_config):
        mock_s3_client.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": "foo/bar.json"}]}
        ]
        result = s3_repo._list_objects("foo/")
        assert "foo/bar.json" in result

    def test__list_objects_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_paginator.return_value.paginate.side_effect = Exception("fail")
        result = s3_repo._list_objects("foo/")
        assert result == []

    def test_get_signature_entry_success(mock_s3_client, mock_config, mock_logger):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"1": {"style": "s", "s3_key": "k"}}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        style, sig = s3_repo.get_signature_entry("user", "track1", "1")
        assert style == "s"
        assert sig == "k"

    def test_get_signature_entry_no_party(mock_s3_client, mock_config, mock_logger):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        style, sig = s3_repo.get_signature_entry("user", "track1", "1")
        assert style == ""
        assert sig == ""

    def test_get_signature_entry_client_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        style, sig = s3_repo.get_signature_entry("user", "track1", "1")
        assert style == ""
        assert sig == ""

    def test_get_signature_entry_other_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_object.side_effect = Exception("fail")
        style, sig = s3_repo.get_signature_entry("user", "track1", "1")
        assert style == ""
        assert sig == ""

    def test_get_folder_size_success(mock_s3_client, mock_config):
        mock_s3_client.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Size": 100}, {"Size": 200}]}
        ]
        result = s3_repo.get_folder_size("user")
        assert result == 300

    def test_get_folder_size_empty(mock_s3_client, mock_config):
        mock_s3_client.get_paginator.return_value.paginate.return_value = []
        result = s3_repo.get_folder_size("user")
        assert result == 0

    def test_get_folder_size_error(mock_s3_client, mock_config):
        mock_s3_client.get_paginator.return_value.paginate.side_effect = Exception("fail")
        with pytest.raises(Exception):
            s3_repo.get_folder_size("user")

    def test_render_sign_update(monkeypatch, mock_s3_client, mock_config):
        class DummyCipher:
            def __init__(self, email): pass
            def encrypt(self, content): return b"enc"
        monkeypatch.setattr(s3_repo, "AESCipher", DummyCipher)
        result = s3_repo.render_sign_update("user", b"pdfbytes", "track1", "doc1")
        assert isinstance(result, str)

    def test_get_signed_success(monkeypatch, mock_s3_client, mock_config):
        class DummyCipher:
            def __init__(self, email): pass
            def decrypt(self, content): return b"decrypted"
        monkeypatch.setattr(s3_repo, "AESCipher", DummyCipher)
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"encrypted"
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_signed("user", "track1", "doc1")
        assert result == b"decrypted"

    def test_get_signed_no_credentials(mock_s3_client, mock_config):
        mock_s3_client.get_object.side_effect = NoCredentialsError()
        with pytest.raises(HTTPException):
            s3_repo.get_signed("user", "track1", "doc1")

    def test_get_signed_client_error_nosuchkey(mock_s3_client, mock_config):
        error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        with pytest.raises(HTTPException) as exc:
            s3_repo.get_signed("user", "track1", "doc1")
        assert exc.value.status_code == 404

    def test_get_signed_client_error_nosuchbucket(mock_s3_client, mock_config):
        error = ClientError({"Error": {"Code": "NoSuchBucket"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        with pytest.raises(HTTPException) as exc:
            s3_repo.get_signed("user", "track1", "doc1")
        assert exc.value.status_code == 500

    def test_get_signed_client_error_other(mock_s3_client, mock_config):
        error = ClientError({"Error": {"Code": "Other"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        with pytest.raises(HTTPException) as exc:
            s3_repo.get_signed("user", "track1", "doc1")
        assert exc.value.status_code == 500

    def test_get_signed_other_error(mock_s3_client, mock_config):
        mock_s3_client.get_object.side_effect = Exception("fail")
        with pytest.raises(HTTPException):
            s3_repo.get_signed("user", "track1", "doc1")
        # Patch NoSuchKey
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        error_response = {'Error': {'Code': 'NoSuchKey', 'Message': 'Not found'}}
        mock_s3_client.get_object.side_effect = [ClientError(error_response, 'GetObject'), ClientError(error_response, 'GetObject')]
        doc_data = MagicMock()
        doc_data.document_id = "doc1"
        tracking_data = {"tracking_id": "track1", "fields": [{"f": 1}], "parties": [{"p": 1}]}
        s3_repo.upload_meta_s3("user", doc_data, tracking_data, defaults=True)
        assert mock_s3_client.put_object.call_count == 2

    def test_upload_meta_s3_existing(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        doc_obj = {'Body': MagicMock()}
        doc_obj['Body'].read.return_value = json.dumps({"document_id": "doc1", "trackings": {}}).encode()
        track_obj = {'Body': MagicMock()}
        track_obj['Body'].read.return_value = json.dumps({"tracking_id": "track1"}).encode()
        mock_s3_client.get_object.side_effect = [doc_obj, track_obj]
        doc_data = MagicMock()
        doc_data.document_id = "doc1"
        tracking_data = {"tracking_id": "track1"}
        s3_repo.upload_meta_s3("user", doc_data, tracking_data, defaults=False)
        assert mock_s3_client.put_object.call_count == 2

    def test_upload_meta_s3_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_object.side_effect = Exception("fail")
        doc_data = MagicMock()
        doc_data.document_id = "doc1"
        tracking_data = {"tracking_id": "track1"}
        with pytest.raises(HTTPException):
            s3_repo.upload_meta_s3("user", doc_data, tracking_data, defaults=False)

    def test_get_doc_meta_success(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "user/metadata/document/doc1.json"}]
        }
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"document_id": "doc1"}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_doc_meta("user")
        assert "doc1" in result

    def test_get_doc_meta_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.list_objects_v2.side_effect = Exception("fail")
        with pytest.raises(HTTPException):
            s3_repo.get_doc_meta("user")

    def test_store_tracking_metadata_success(mock_s3_client, mock_config, mock_logger):
        s3_repo.store_tracking_metadata("user", "doc1", "track1", {"foo": "bar"})
        assert mock_s3_client.put_object.called

    def test_store_tracking_metadata_client_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.put_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "PutObject")
        with pytest.raises(ClientError):
            s3_repo.store_tracking_metadata("user", "doc1", "track1", {"foo": "bar"})

    def test_store_tracking_metadata_other_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.put_object.side_effect = Exception("fail")
        with pytest.raises(Exception):
            s3_repo.store_tracking_metadata("user", "doc1", "track1", {"foo": "bar"})

    def test_load_all_json_from_prefix_success(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "user/metadata/document/doc1.json"}]
        }
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"foo": "bar"}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.load_all_json_from_prefix("user")
        assert result[0]["foo"] == "bar"

    def test_load_all_json_from_prefix_invalid_json(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "user/metadata/document/doc1.json"}]
        }
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"{invalid"
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.load_all_json_from_prefix("user")
        assert result == []

    def test_load_all_json_from_prefix_client_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.list_objects_v2.side_effect = ClientError({"Error": {"Code": "fail"}}, "ListObjectsV2")
        with pytest.raises(ClientError):
            s3_repo.load_all_json_from_prefix("user")

    def test_s3_file_responses_success(mock_s3_client, mock_config, mock_logger):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"hello"
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.s3_file_responses("user", "foo/bar.json")
        assert result == "hello"

    def test_s3_file_responses_no_such_key(mock_s3_client, mock_config, mock_logger):
        error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        result = s3_repo.s3_file_responses("user", "foo/bar.json")
        assert result == "{}"

    def test_s3_file_responses_other_client_error(mock_s3_client, mock_config, mock_logger):
        error = ClientError({"Error": {"Code": "Other"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        with pytest.raises(ClientError):
            s3_repo.s3_file_responses("user", "foo/bar.json")

    def test_s3_file_responses_other_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_object.side_effect = Exception("fail")
        with pytest.raises(Exception):
            s3_repo.s3_file_responses("user", "foo/bar.json")

    def test_store_status_success(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"trackings": {}}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        s3_repo.store_status("doc1", {"trackings": {"t1": {"tracking_status": "completed"}}}, "user")
        assert mock_s3_client.put_object.called

    def test_store_status_no_such_key(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        s3_repo.store_status("doc1", {"trackings": {"t1": {"tracking_status": "completed"}}}, "user")
        assert mock_s3_client.put_object.called

    def test_store_status_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_object.side_effect = Exception("fail")
        with pytest.raises(HTTPException):
            s3_repo.store_status("doc1", {"trackings": {"t1": {"tracking_status": "completed"}}}, "user")

    def test_save_defaults_success(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        s3_repo.save_defaults("user", "doc1", [{"field": "f"}])
        assert mock_s3_client.put_object.called

    def test_save_defaults_existing(mock_s3_client, mock_config, mock_logger):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"defaults": {}}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        s3_repo.save_defaults("user", "doc1", [{"field": "f"}])
        assert mock_s3_client.put_object.called

    def test_save_defaults_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_object.side_effect = Exception("fail")
        with pytest.raises(HTTPException):
            s3_repo.save_defaults("user", "doc1", [{"field": "f"}])

    def test_save_templates_success(mock_s3_client, mock_config, mock_logger):
        s3_repo.save_templates("user", "doc1", {"foo": "bar"})
        assert mock_s3_client.put_object.called

    def test_save_templates_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.put_object.side_effect = Exception("fail")
        with pytest.raises(HTTPException):
            s3_repo.save_templates("user", "doc1", {"foo": "bar"})

    def test_get_pdf_s3_success(monkeypatch, mock_s3_client, mock_config):
        class DummyCipher:
            def __init__(self, email): pass
            def decrypt(self, content): return b"decrypted"
        monkeypatch.setattr(s3_repo, "AESCipher", DummyCipher)
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"encrypted"
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_pdf_s3("user", "foo/bar.pdf")
        assert result == b"decrypted"

    def test_get_index_s3_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"foo": "bar"}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_index_s3("user")
        assert result == {"foo": "bar"}

    def test_delete_s3_success(mock_s3_client, mock_config):
        s3_repo.delete_s3("foo/bar.pdf")
        assert mock_s3_client.delete_object.called

    def test_put_folder_creates_keep(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {"Contents": []}
        s3_repo.put_folder("user/files/folder/file.pdf")
        assert mock_s3_client.put_object.called

    def test_put_new_folder_creates_keep(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {"Contents": []}
        s3_repo.put_new_folder("user/files/folder/file.pdf")
        assert mock_s3_client.put_object.called

    def test_get_s3_js_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"foo": "bar"}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_s3_js("user/index/document_index.json")
        assert result == {"foo": "bar"}

    def test_copy_data_s3_success(monkeypatch, mock_s3_client, mock_config):
        def is_file_key(key): return True
        def ensure_folder_exists_after_deletion(key): pass
        monkeypatch.setattr(s3_repo, "get_s3_js", lambda key: {
            "doc1": {"file_path": "f1", "metadata_path": "m1", "fileName": "f.pdf"}
        })
        mock_s3_client.copy_object.return_value = None
        mock_s3_client.delete_object.return_value = None
        results = {}
        out = s3_repo.copy_data_s3(["doc1"], "user", ensure_folder_exists_after_deletion, is_file_key, "new", results)
        assert results["doc1"]["status"] == "moved"

    def test_get_s3_meta_obj_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"foo": "bar"}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_s3_meta_obj("foo/bar.json")
        assert result == {"foo": "bar"}

    def test_update_doc_s3_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"data"
        mock_s3_client.get_object.return_value = mock_obj
        key, raw = s3_repo.update_doc_s3("user")
        assert key.endswith("document_index.json")
        assert raw == b"data"

    def test_get_s3_update_doc_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"foo": "bar"}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        data, key = s3_repo.get_s3_update_doc("user")
        assert data == {"foo": "bar"}

    def test_get_s3_update_doc_unicode_error(mock_s3_client, mock_config, mock_logger):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"\xff"
        mock_s3_client.get_object.return_value = mock_obj
        with pytest.raises(Exception):
            s3_repo.get_s3_update_doc("user")

    def test_get_s3_update_doc_json_error(mock_s3_client, mock_config, mock_logger):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"{invalid"
        mock_s3_client.get_object.return_value = mock_obj
        with pytest.raises(Exception):
            s3_repo.get_s3_update_doc("user")

    def test_get_encrypted_file_overwrite_false(monkeypatch, mock_s3_client, mock_config):
        class DummyCipher:
            def __init__(self, email): pass
            def encrypt(self, content): return b"enc"
        monkeypatch.setattr(s3_repo, "AESCipher", DummyCipher)
        mock_s3_client.head_object.return_value = None
        with pytest.raises(HTTPException):
            s3_repo.get_encrypted_file("user", MagicMock(filename="f.pdf"), b"abc", False, "foo/bar.pdf")

    def test_get_encrypted_file_overwrite_true(monkeypatch, mock_s3_client, mock_config):
        class DummyCipher:
            def __init__(self, email): pass
            def encrypt(self, content): return b"enc"
        monkeypatch.setattr(s3_repo, "AESCipher", DummyCipher)
        mock_s3_client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
        s3_repo.get_encrypted_file("user", MagicMock(filename="f.pdf"), b"abc", True, "foo/bar.pdf")
        assert mock_s3_client.put_object.called

    def test__get_metadata_key_and_pdf_key():
        assert s3_repo._get_metadata_key("user", "doc1", "prefix") == "user/files/prefix/doc1.json"
        assert s3_repo._get_pdf_key("user", "file.pdf", "prefix") == "user/files/prefix/file.pdf"

    def test_udpate_meta_doc(monkeypatch, mock_s3_client, mock_config):
        class DummyCipher:
            def __init__(self, email): pass
            def encrypt(self, content): return b"enc"
        monkeypatch.setattr(s3_repo, "AESCipher", DummyCipher)
        file = MagicMock()
        file.filename = "file.pdf"
        file.content_type = "application/pdf"
        file.file = MagicMock()
        file.file.seek = MagicMock()
        file.file.tell = MagicMock(return_value=100)
        file.file.read = MagicMock(return_value=b"abc")
        result = s3_repo.udpate_meta_doc("doc1", "user", file, True, "prefix")
        assert result["fileName"] == "file.pdf"

    def test_append_logs_new_file(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        mock_s3_client.put_object.return_value = None
        s3_repo.append_logs({"foo": "bar"}, "foo/bar.json")
        assert mock_s3_client.put_object.called

    def test_append_logs_existing(mock_s3_client, mock_config, mock_logger):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps([{"foo": "bar"}]).encode()
        mock_s3_client.get_object.return_value = mock_obj
        s3_repo.append_logs({"baz": "qux"}, "foo/bar.json")
        assert mock_s3_client.put_object.called

    def test_get_logs_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps([{"foo": "bar"}]).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_logs("foo/bar.json")
        assert result[0]["foo"] == "bar"

    @pytest.mark.asyncio
    async def test_s3_head_upload_success(mock_s3_client, mock_config):
        mock_s3_client.head_object.return_value = None
        await s3_repo.s3_head_upload("foo/bar.pdf")
        assert mock_s3_client.head_object.called

    def test_recursive_list_success(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {"Contents": []}
        result = s3_repo.recursive_list("user")
        assert isinstance(result, dict)

    def test_s3_update_success(mock_s3_client, mock_config):
        s3_repo.s3_update("user", {"foo": "bar"})
        assert mock_s3_client.put_object.called

    def test_get_document_index_success(mock_s3_client, mock_config):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"doc1": {"file_path": "foo/bar.pdf"}}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_document_index("user")
        assert result["foo/bar.pdf"] == "doc1"

    def test_get_document_index_no_such_key(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        result = s3_repo.get_document_index("user")
        assert result == {}

    def test_get_document_index_other_error(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        mock_s3_client.get_object.side_effect = Exception("fail")
        result = s3_repo.get_document_index("user")
        assert result == {}

    def test_list_objects_recursive_success(monkeypatch, mock_s3_client, mock_config):
        monkeypatch.setattr(s3_repo, "get_document_index", lambda email: {"foo/bar.pdf": "doc1"})
        mock_s3_client.list_objects_v2.return_value = {
            "CommonPrefixes": [],
            "Contents": [{"Key": "foo/bar.pdf"}]
        }
        result = s3_repo.list_objects_recursive("user", "foo/")
        assert result[0]["type"] == "file"

    def test_delete_folder_success(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "user/files/folder/.keep"}]
        }
        result = s3_repo.delete_folder("user", "folder")
        assert result["status"] == "folder deleted"

    def test_delete_folder_non_keep_files(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "user/files/folder/file.pdf"}]
        }
        result = s3_repo.delete_folder("user", "folder")
        assert "denied" in result["detail"]

    def test_delete_folder_error(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.side_effect = ClientError({"Error": {"Code": "fail"}}, "ListObjectsV2")
        result = s3_repo.delete_folder("user", "folder")
        assert result["status"] == "error"

    def test_create_folder_only_success(mock_s3_client, mock_config):
        mock_s3_client.put_object.return_value = None
        result = s3_repo.create_folder_only("user", "folder")
        assert result["status"] == "folder created"

    def test_create_folder_only_error(mock_s3_client, mock_config):
        mock_s3_client.put_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "PutObject")
        result = s3_repo.create_folder_only("user", "folder")
        assert "error" in result

    def test_get_file_name_success(monkeypatch):
        class DummyStorage:
            def get(self, email, document_id): return {"fileName": "foo.pdf"}
        monkeypatch.setattr("app.api.routes.files_api.get_storage", lambda t: DummyStorage())
        assert s3_repo.get_file_name("user", "doc1") == "foo.pdf"

    def test_get_file_name_not_found(monkeypatch):
        class DummyStorage:
            def get(self, email, document_id): return {}
        monkeypatch.setattr("app.api.routes.files_api.get_storage", lambda t: DummyStorage())
        with pytest.raises(HTTPException):
            s3_repo.get_file_name("user", "doc1")

    def test_get_file_name_error(monkeypatch):
        monkeypatch.setattr("app.api.routes.files_api.get_storage", lambda t: (_ for _ in ()).throw(Exception("fail")))
        with pytest.raises(HTTPException):
            s3_repo.get_file_name("user", "doc1")

    def test_rendered_sign_s3_success(monkeypatch, mock_s3_client, mock_config):
        class DummyStorage:
            def get(self, email, document_id): return {
                "metadata_path": "foo/meta.json", "fileName": "foo.pdf", "file_path": "foo/bar.pdf"
            }
        monkeypatch.setattr("app.api.routes.files_api.get_storage", lambda t: DummyStorage())
        monkeypatch.setattr(s3_repo, "AESCipher", lambda email: MagicMock(decrypt=lambda x: b"pdf"))
        mock_s3_client.generate_presigned_url.return_value = "http://example.com"
        monkeypatch.setattr(s3_repo.requests, "get", lambda url: MagicMock(json=lambda: {}, raise_for_status=lambda: None))
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"encrypted"
        mock_s3_client.get_object.return_value = mock_obj
        monkeypatch.setattr(s3_repo.fitz, "open", lambda stream, filetype: "pdfdoc")
        doc, fname = s3_repo.rendered_sign_s3("user", "doc1")
        assert fname == "foo.pdf"

    def test_rendered_sign_s3_error(monkeypatch):
        monkeypatch.setattr("app.api.routes.files_api.get_storage", lambda t: (_ for _ in ()).throw(Exception("fail")))
        with pytest.raises(Exception):
            s3_repo.rendered_sign_s3("user", "doc1")

    def test_render_sign_update(monkeypatch, mock_s3_client, mock_config):
        class DummyCipher:
            def __init__(self, email): pass
            def encrypt(self, content): return b"enc"
        monkeypatch.setattr(s3_repo, "AESCipher", DummyCipher)
        result = s3_repo.render_sign_update("user", b"pdfbytes", "track1", "doc1")
        assert isinstance(result, str)

    def test_get_signed_success(monkeypatch, mock_s3_client, mock_config):
        class DummyCipher:
            def __init__(self, email): pass
            def decrypt(self, content): return b"decrypted"
        monkeypatch.setattr(s3_repo, "AESCipher", DummyCipher)
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"encrypted"
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_signed("user", "track1", "doc1")
        assert result == b"decrypted"

    def test_get_signed_no_credentials(mock_s3_client, mock_config):
        mock_s3_client.get_object.side_effect = NoCredentialsError()
        with pytest.raises(HTTPException):
            s3_repo.get_signed("user", "track1", "doc1")

    def test_get_signed_client_error_nosuchkey(mock_s3_client, mock_config):
        error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        with pytest.raises(HTTPException) as exc:
            s3_repo.get_signed("user", "track1", "doc1")
        assert exc.value.status_code == 404

    def test_get_signed_client_error_nosuchbucket(mock_s3_client, mock_config):
        error = ClientError({"Error": {"Code": "NoSuchBucket"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        with pytest.raises(HTTPException) as exc:
            s3_repo.get_signed("user", "track1", "doc1")
        assert exc.value.status_code == 500

    def test_get_signed_client_error_other(mock_s3_client, mock_config):
        error = ClientError({"Error": {"Code": "Other"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        with pytest.raises(HTTPException) as exc:
            s3_repo.get_signed("user", "track1", "doc1")
        assert exc.value.status_code == 500

    def test_get_signed_other_error(mock_s3_client, mock_config):
        mock_s3_client.get_object.side_effect = Exception("fail")
        with pytest.raises(HTTPException):
            s3_repo.get_signed("user", "track1", "doc1")

    def test_get_document_name_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"doc1": {"fileName": "foo.pdf"}}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_document_name("user", "doc1")
        assert result == "foo.pdf"

    def test_get_document_name_not_found(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.get_document_name("user", "doc1")
        assert result is None

    def test_get_document_name_error(mock_s3_client, mock_config):
        mock_s3_client.get_object.side_effect = Exception("fail")
        result = s3_repo.get_document_name("user", "doc1")
        assert result is None

    def test_upload_file(monkeypatch, mock_s3_client, mock_config):
        class DummyCipher:
            def __init__(self, email): pass
            def encrypt(self, content): return b"enc"
        monkeypatch.setattr(s3_repo, "AESCipher", DummyCipher)
        s3_repo.upload_file("user", b"bytes", "doc1", "track1")
        assert mock_s3_client.put_object.called

    def test_get_folder_size(mock_s3_client, mock_config):
        mock_s3_client.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Size": 100}, {"Size": 200}]}
        ]
        result = s3_repo.get_folder_size("user")
        assert result == 300

    def test_s3_download_string(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"hello"
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.s3_download_string("foo/bar.json")
        assert result == "hello"

    def test_get_signature_entry_success(mock_s3_client, mock_config, mock_logger):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"1": {"style": "s", "s3_key": "k"}}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        style, sig = s3_repo.get_signature_entry("user", "track1", "1")
        assert style == "s"
        assert sig == "k"

    def test_get_signature_entry_no_party(mock_s3_client, mock_config, mock_logger):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        style, sig = s3_repo.get_signature_entry("user", "track1", "1")
        assert style == ""
        assert sig == ""

    def test_get_signature_entry_client_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        style, sig = s3_repo.get_signature_entry("user", "track1", "1")
        assert style == ""
        assert sig == ""

    def test_get_signature_entry_other_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_object.side_effect = Exception("fail")
        style, sig = s3_repo.get_signature_entry("user", "track1", "1")
        assert style == ""
        assert sig == ""

    def test_s3_delete_object(mock_s3_client, mock_config):
        s3_repo.s3_delete_object("foo/bar.json")
        assert mock_s3_client.delete_object.called

    def test_s3_upload_bytes_success(mock_s3_client, mock_config):
        assert s3_repo.s3_upload_bytes(b"bytes", "foo/bar.json", "application/json")

    def test_s3_upload_bytes_client_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.put_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "PutObject")
        assert not s3_repo.s3_upload_bytes(b"bytes", "foo/bar.json", "application/json")

    def test_s3_upload_json_success(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_upload_json({"foo": "bar"}, "foo/bar.json")
        assert mock_s3_client.put_object.called

    def test_s3_upload_json_client_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.put_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "PutObject")
        with pytest.raises(ClientError):
            s3_repo.s3_upload_json({"foo": "bar"}, "foo/bar.json")

    def test_s3_download_json_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"foo": "bar"}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.s3_download_json("foo/bar.json")
        assert result == {"foo": "bar"}

    def test_s3_download_json_no_such_key(mock_s3_client, mock_config):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        mock_s3_client.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        result = s3_repo.s3_download_json("foo/bar.json")
        assert result is None

    def test_s3_download_json_client_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "GetObject")
        with pytest.raises(ClientError):
            s3_repo.s3_download_json("foo/bar.json")

    def test_s3_delete_objects_success(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_delete_objects("foo/bar.json")
        assert mock_s3_client.delete_object.called

    def test_s3_delete_objects_client_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.delete_object.side_effect = ClientError({"Error": {"Code": "fail"}}, "DeleteObject")
        with pytest.raises(ClientError):
            s3_repo.s3_delete_objects("foo/bar.json")

    def test_s3_list_objects_success(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "foo/bar.json"}, {"Key": "foo/baz.txt"}]
        }
        result = s3_repo.s3_list_objects("foo/")
        assert "foo/bar.json" in result

    def test_s3_list_objects_no_contents(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {}
        result = s3_repo.s3_list_objects("foo/")
        assert result == []

    def test_s3_list_object_success(mock_s3_client, mock_config):
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "foo/bar.json"}, {"Key": "foo/baz.txt"}]
        }
        result = s3_repo.s3_list_object("foo/")
        assert "foo/bar.json" in result

    def test_s3_download_bytes_success(mock_s3_client, mock_config):
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = b"bytes"
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.s3_download_bytes("foo/bar.json")
        assert result == b"bytes"

    def test__list_objects_success(mock_s3_client, mock_config):
        mock_s3_client.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": "foo/bar.json"}]}
        ]
        result = s3_repo._list_objects("foo/")
        assert "foo/bar.json" in result

    def test__list_objects_error(mock_s3_client, mock_config, mock_logger):
        mock_s3_client.get_paginator.return_value.paginate.side_effect = Exception("fail")
        result = s3_repo._list_objects("foo/")
        assert result == []

    def test_load_tracking_metadata_by_tracking_id_success(mock_s3_client, mock_config):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"CommonPrefixes": [{"Prefix": "user/metadata/tracking/doc1/"}]}
        ]
        mock_s3_client.get_paginator.return_value = paginator
        mock_obj = {'Body': MagicMock()}
        mock_obj['Body'].read.return_value = json.dumps({"foo": "bar"}).encode()
        mock_s3_client.get_object.return_value = mock_obj
        result = s3_repo.load_tracking_metadata_by_tracking_id("user", "track1")
        assert result["document_id"] == "doc1"

    def test_load_tracking_metadata_by_tracking_id_not_found(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"CommonPrefixes": [{"Prefix": "user/metadata/tracking/doc1/"}]}
        ]
        mock_s3_client.get_paginator.return_value = paginator
        error = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        mock_s3_client.get_object.side_effect = error
        with pytest.raises(HTTPException) as exc:
            s3_repo.load_tracking_metadata_by_tracking_id("user", "track1")
        assert exc.value.status_code == 404

    def test_load_tracking_metadata_by_tracking_id_error(mock_s3_client, mock_config, mock_logger):
        s3_repo.s3_client.exceptions = type("MockExceptions", (), {"NoSuchKey": ClientError})
        paginator = MagicMock()
        paginator.paginate.side_effect = Exception("fail")
        mock_s3_client.get_paginator.return_value = paginator
        with pytest.raises(HTTPException):
            s3_repo.load_tracking_metadata_by_tracking_id("user", "track1")