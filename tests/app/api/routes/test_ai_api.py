import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI, HTTPException
from app.api.routes.ai_api import router
from auth_app.app.api.routes.deps import dynamic_permission_check
from unittest.mock import MagicMock
import sys

# Patch the db before importing any app code that uses it
mock_db_module = MagicMock()
sys.modules['auth_app.app.database.connection'] = mock_db_module
mock_db_module.db = MagicMock()

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
from auth_app.app.api.routes import users as users_module

@pytest.fixture
def client():
    app = FastAPI()
    # Override the permission dependency to always allow
    app.dependency_overrides[dynamic_permission_check] = lambda: True
    app.include_router(router)
    return TestClient(app)

def test_summarize_success(client, tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"PDF content")
    with patch("app.services.ai_service.AIService.summarize", new=AsyncMock(return_value={"summary": "Test summary"})):
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/ai-assistants/summarize",
                files={"pdf": ("test.pdf", f, "application/pdf")}
            )
    assert response.status_code == 200
    assert response.json() == {"summary": "Test summary"}

def test_summarize_no_file(client):
    response = client.post("/ai-assistants/summarize")
    assert response.status_code == 422

def test_summarize_internal_error(client, tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"PDF content")
    with patch("app.services.ai_service.AIService.summarize", new=AsyncMock(side_effect=Exception("fail"))):
        with open(pdf_path, "rb") as f:
            with pytest.raises(Exception):
                client.post(
                    "/ai-assistants/summarize",
                    files={"pdf": ("test.pdf", f, "application/pdf")}
                )

def test_ask_pdf_success(client, tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"PDF content")
    with patch("app.services.ai_service.AIService.ask_pdf", new=AsyncMock(return_value={"answer": "42"})):
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/ai-assistants/ask-pdf",
                files={"pdf": ("test.pdf", f, "application/pdf")},
                data={"question": "What is the answer?"}
            )
    assert response.status_code == 200
    assert response.json() == {"answer": "42"}

def test_ask_pdf_missing_fields(client):
    response = client.post("/ai-assistants/ask-pdf")
    assert response.status_code == 422

def test_ask_pdf_internal_error(client, tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"PDF content")
    with patch("app.services.ai_service.AIService.ask_pdf", new=AsyncMock(side_effect=Exception("fail"))):
        with open(pdf_path, "rb") as f:
            with pytest.raises(Exception):
                client.post(
                    "/ai-assistants/ask-pdf",
                    files={"pdf": ("test.pdf", f, "application/pdf")},
                    data={"question": "What is the answer?"}
                )

def test_generate_success(client):
    with patch("app.services.ai_service.AIService.generate", new=AsyncMock(return_value={"result": "Generated"})):
        payload = {"prompt": "Say hi", "type": "text"}
        response = client.post("/ai-assistants/generate", json=payload)
        assert response.status_code == 200
        assert response.json() == {"result": "Generated"}

def test_generate_missing_fields(client):
    response = client.post("/ai-assistants/generate", json={})
    assert response.status_code == 422

def test_generate_internal_error(client):
    with patch("app.services.ai_service.AIService.generate", new=AsyncMock(side_effect=Exception("fail"))):
        payload = {"prompt": "Say hi", "type": "text"}
        with pytest.raises(Exception):
            client.post("/ai-assistants/generate", json=payload)
def test_permission_denied(tmp_path):
    def deny_permission():
        raise HTTPException(status_code=403, detail="Forbidden")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[dynamic_permission_check] = deny_permission
    test_client = TestClient(app)
    response = test_client.post("/ai-assistants/generate", json={"prompt": "Say hi", "type": "text"})
    assert response.status_code == 403