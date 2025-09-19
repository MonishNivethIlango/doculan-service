from unittest.mock import patch, MagicMock
import pytest
from DataAccessLayer.storage.storage_factory import get_storage_strategy

@patch('DataAccessLayer.storage.storage_factory.config')
@patch('DataAccessLayer.storage.storage_factory.S3Storage')
def test_get_storage_strategy_s3(mock_s3, mock_config):
    mock_config.S3_BUCKET = 'bucket'
    instance = MagicMock()
    mock_s3.return_value = instance
    result = get_storage_strategy('s3')
    assert result == instance
    mock_s3.assert_called_with(bucket_name='bucket')

@patch('DataAccessLayer.storage.storage_factory.GoogleDriveStorage')
def test_get_storage_strategy_gdrive(mock_gdrive):
    instance = MagicMock()
    mock_gdrive.return_value = instance
    result = get_storage_strategy('gdrive')
    assert result == instance
    mock_gdrive.assert_called()

def test_get_storage_strategy_invalid():
    with pytest.raises(ValueError):
        get_storage_strategy('invalid')
