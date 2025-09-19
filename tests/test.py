from unittest.mock import patch, MagicMock
import pytest

from app.schemas.tracking_schemas import SignField
from app.services.signature_service import SignatureHandler
from fastapi import FastAPI
from fastapi.testclient import TestClient

@pytest.fixture
def dummy_request():
    app = FastAPI()
    client = TestClient(app)
    return client.build_request("POST", "/sign")

@patch("auth_app.app.database.connection.async_client")
@patch("auth_app.app.database.connection.DB_NAME", "testdb")
def test_sign_field_success(mock_client, dummy_request):
    # Mock MongoDB database access
    mock_db = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    data = SignField(
        document_id="doc-123",
        tracking_id="track-456",
        party_id="party-789"
    )
    result = SignatureHandler.sign_field("user@example.com", data, dummy_request)
    assert result["status"] == "success"
    assert result["signed"] is True
