from unittest.mock import patch, MagicMock
from DataAccessLayer.storage.gdrive_storage import GoogleDriveStorage


# Dummy subclass for testing
class TestGoogleDriveStorage(GoogleDriveStorage):
    def move_file(self, src, dest):
        pass  # Dummy implementation for abstract method


@patch('DataAccessLayer.storage.gdrive_storage.service_account.Credentials')
@patch('DataAccessLayer.storage.gdrive_storage.build')
def test_upload_file(mock_build, mock_creds):
    # Arrange
    service = MagicMock()
    files_create = service.files.return_value.create
    files_create.return_value.execute.return_value = {'id': 'fileid123'}
    mock_build.return_value = service
    mock_creds.from_service_account_file.return_value = 'creds'

    storage = TestGoogleDriveStorage()

    file_mock = MagicMock()
    file_mock.file = MagicMock()
    file_mock.content_type = 'application/pdf'

    # Act
    result = storage.upload_file(file_mock, 'test.pdf')

    # Assert
    assert result['message'] == 'Uploaded to Google Drive'
    assert result['file_id'] == 'fileid123'
    files_create.assert_called()


@patch('DataAccessLayer.storage.gdrive_storage.service_account.Credentials')
@patch('DataAccessLayer.storage.gdrive_storage.build')
def test_get_file(mock_build, mock_creds):
    # Arrange
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {
        'files': [{'id': 'fileid', 'name': 'test.pdf'}]
    }
    get_media = service.files.return_value.get_media
    mock_build.return_value = service
    mock_creds.from_service_account_file.return_value = 'creds'

    storage = TestGoogleDriveStorage()

    # Patch MediaIoBaseDownload
    with patch('DataAccessLayer.storage.gdrive_storage.MediaIoBaseDownload') as mock_downloader:
        downloader_instance = mock_downloader.return_value
        downloader_instance.next_chunk.side_effect = [(None, True)]

        # Act
        result = storage.get_file('test.pdf')

        # Assert
        assert result['filename'] == 'test.pdf'
        assert 'content' in result
        get_media.assert_called_with(fileId='fileid')
