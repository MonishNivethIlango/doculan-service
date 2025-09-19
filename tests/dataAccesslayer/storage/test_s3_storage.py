import json
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from DataAccessLayer.storage.s3_storage import S3Storage


@patch('DataAccessLayer.storage.s3_storage.s3_client')
@patch('DataAccessLayer.storage.s3_storage.AESCipher')
@patch('DataAccessLayer.storage.s3_storage.config')
def test_upload_file(mock_config, mock_cipher, mock_s3):
    # Patch NoSuchKey to point to ClientError to avoid TypeError in 'except'
    mock_s3.exceptions = MagicMock()
    mock_s3.exceptions.NoSuchKey = ClientError

    # Arrange
    mock_config.KMS_KEY_ID = 'kmsid'
    mock_cipher.return_value.encrypt.return_value = b'encrypted'

    # Simulate head_object raising 404 error (file doesn't exist yet)
    head_error = {
        'Error': {'Code': '404', 'Message': 'Not Found'}
    }
    mock_s3.head_object.side_effect = ClientError(head_error, 'HeadObject')

    # Simulate get_object raising NoSuchKey only for the index file
    def mock_get_object(Bucket, Key):
        if Key.endswith('index/document_index.json'):
            raise ClientError(
                {'Error': {'Code': 'NoSuchKey', 'Message': 'Key does not exist'}},
                'GetObject'
            )
        return {'Body': MagicMock(read=lambda: b'some content')}

    mock_s3.get_object.side_effect = mock_get_object
    mock_s3.put_object.return_value = None  # simulate successful put

    storage = S3Storage('bucket')

    file_mock = MagicMock()
    file_mock.filename = 'file.pdf'
    file_mock.file.read.return_value = b'data'
    file_mock.file.tell.return_value = 4
    file_mock.file.seek.return_value = None
    file_mock.content_type = 'application/pdf'

    # Act
    result = storage.upload_file('user@example.com', 'docid', file_mock)

    # Assert
    assert result['uploaded'] is True
    assert result['document_id'] == 'docid'
    assert 's3_keys' in result
    mock_s3.put_object.assert_called()

@patch('DataAccessLayer.storage.s3_storage.s3_client')
@patch('DataAccessLayer.storage.s3_storage.AESCipher')
def test_get_file(mock_cipher, mock_s3):
    # Arrange
    storage = S3Storage('bucket')

    # Simulate file found in index
    mock_s3.get_object.return_value = {
        'Body': MagicMock(read=lambda: json.dumps({
            'docid': {
                'file_path': 'path',
                'metadata_path': 'meta',
                'fileName': 'file.pdf'
            }
        }).encode('utf-8'))
    }

    result = storage.get_file('user@example.com', 'docid')
    assert result['document_id'] == 'docid'
    assert result['file_path'] == 'path'

    # Simulate not found
    mock_s3.get_object.return_value = {
        'Body': MagicMock(read=lambda: b'{}')
    }

    result = storage.get_file('user@example.com', 'docid')
    assert result['error'] == 'Document ID not found in index'
