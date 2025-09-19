import os
import builtins
from importlib import reload
from unittest import mock
import sys
import pytest


@pytest.fixture
def mock_env_vars():
    with mock.patch.dict(os.environ, {
        "S3_BUCKET": "test-bucket",
        "HOST": "http://localhost",
        "MONGO_URI": "mongodb://mockuri",
        "MONGO_DB": "testdb",
        "AWS_ACCESS_KEY": "/fake/path/access_key.txt",
        "AWS_SECRET_KEY": "/fake/path/secret_key.txt",
        "GOOGLE_SERVICE_ACCOUNT": "some-service-account",
        "MAIL_USERNAME": "user@example.com",
        "MAIL_PASSWORD": "password123",
        "MAIL_FROM": "no-reply@example.com",
        "MAIL_PORT": "465",
        "MAIL_SERVER": "smtp.example.com",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6380",
        "REDIS_DB": "1",
        "KMS_KEY_ID": "/fake/path/kms_key.txt",
        "KEY": "/fake/path/key.txt",
        "IV": "/fake/path/iv.txt",
        "PRIVATE_KEY_PATH": "/fake/path/private.pem",
        "PUBLIC_KEY_PATH": "/fake/path/public.pem",
        "AES_KEY": "aeskey",
        "AES_IV": "aesiv"
    }, clear=True):
        yield


@pytest.fixture
def mock_file_reads():
    # Enhanced mock_open to support encoding and dotenv reads
    def _mock_open(file_path, mode='r', *args, **kwargs):
        mock_file = mock.MagicMock()
        content_map = {
            "/fake/path/access_key.txt": "mock-access-key",
            "/fake/path/secret_key.txt": "mock-secret-key",
            "/fake/path/kms_key.txt": "mock-kms-key",
            "/fake/path/key.txt": "mock-aes-key",
            "/fake/path/iv.txt": "mock-iv",
        }
        # Default content for dotenv or unknown paths
        content = content_map.get(file_path, "SOME_ENV=some_value\n")
        mock_file.__enter__.return_value.read.return_value = content
        return mock_file

    with mock.patch("os.path.exists", return_value=True), \
         mock.patch("os.path.isfile", return_value=True), \
         mock.patch("builtins.open", new=_mock_open):
        yield


def test_config_loads_env_vars(mock_env_vars, mock_file_reads):
    # Reload the config module so class-level env vars are refreshed
    if "config" in sys.modules:
        del sys.modules["config"]

    import config as config_module
    reload(config_module)

    config = config_module.Config()

    assert config.S3_BUCKET == "test-bucket"
    assert config.BASE_URL == "http://localhost"
    assert config.MONGO_URI == "mongodb://mockuri"
    assert config.MONGO_DB == "testdb"
    assert config.AWS_ACCESS_KEY == "mock-access-key"
    assert config.AWS_SECRET_KEY == "mock-secret-key"
    assert config.GOOGLE_SERVICE_ACCOUNT == "some-service-account"
    assert config.MAIL_USERNAME == "user@example.com"
    assert config.MAIL_PASSWORD == "password123"
    assert config.MAIL_FROM == "no-reply@example.com"
    assert config.MAIL_PORT == 465
    assert config.MAIL_SERVER == "smtp.example.com"
    assert config.MAIL_STARTTLS is True
    assert config.MAIL_SSL_TLS is False
    assert config.STORAGE_TYPE == "s3"
    assert config.REDIS_HOST == "localhost"
    assert config.REDIS_PORT == 6380
    assert config.REDIS_DB == 1
    assert config.KMS_KEY_ID == "mock-kms-key"
    assert config.KEY == "mock-aes-key"
    assert config.IV == "mock-iv"
    assert config.PRIVATE_KEY_PATH == "/fake/path/private.pem"
    assert config.PUBLIC_KEY_PATH == "/fake/path/public.pem"
    assert config.AES_KEY == "aeskey"
    assert config.AES_IV == "aesiv"
