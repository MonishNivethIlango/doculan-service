from unittest.mock import patch
import importlib
import os

@patch.dict(os.environ, {
    "AWS_ACCESS_KEY": "key",
    "AWS_SECRET_KEY": "secret",
    "AWS_REGION": "us-east-1"
})
@patch('botocore.config.Config')  # ✅ THIS is the correct patch
@patch('boto3.client')
def test_s3_and_kms_client_init(mock_boto3_client, mock_config_class):
    # Mock the return value of Config()
    mock_config_instance = 'botocfg'
    mock_config_class.return_value = mock_config_instance

    # Reload module to apply patched values
    import database.db_config
    importlib.reload(database.db_config)

    # Assert S3 client call
    mock_boto3_client.assert_any_call(
        's3',
        aws_access_key_id='key',
        aws_secret_access_key='secret',
        region_name='us-east-1',
        config='botocfg'
    )

    # Assert KMS client call
    mock_boto3_client.assert_any_call(
        'kms',
        aws_access_key_id='key',
        aws_secret_access_key='secret',
        region_name='us-east-1'
    )
