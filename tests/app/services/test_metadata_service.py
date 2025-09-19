import base64
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from starlette.responses import FileResponse
from app.services.metadata_service import MetadataService
from app.schemas.tracking_schemas import DocumentRequest, Field, EmailResponse, PdfSize, Holder, Address
from pydantic import ValidationError

@patch("repositories.s3_repo.load_meta_s3")
def test_load_metadata_from_s3_success(mock_load_meta):
    mock_load_meta.return_value = {"key": "value"}
    result = MetadataService.load_metadata_from_s3("test@example.com", "track123", "doc123")
    assert result == {"key": "value"}
    mock_load_meta.assert_called_once()

@patch("repositories.s3_repo.load_meta_s3", side_effect=Exception("S3 Error"))
@patch("app.services.metadata_service.s3_client")
def test_load_metadata_from_s3_failure(mock_s3_client, _):
    class FakeNoSuchKey(Exception):
        pass
    mock_s3_client.exceptions.NoSuchKey = FakeNoSuchKey
    with patch("repositories.s3_repo.load_meta_s3", side_effect=FakeNoSuchKey):
        with pytest.raises(HTTPException) as exc_info:
            MetadataService.load_metadata_from_s3("test@example.com", "track123", "doc123")
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Document metadata not found."

@patch("app.services.metadata_service.MetadataService.get_metadata")
def test_get_email_by_party_id_success(mock_get_metadata):
    mock_get_metadata.return_value = {
        "parties": [{"id": "p1", "email": "p1@example.com"}]
    }
    result = MetadataService.get_email_by_party_id("test@example.com", "track1", "doc1", "p1")
    assert result == {"email": "p1@example.com"}

@patch("app.services.metadata_service.MetadataService.get_metadata")
def test_get_email_by_party_id_party_not_found(mock_get_metadata):
    mock_get_metadata.return_value = {"parties": []}
    with pytest.raises(HTTPException) as exc_info:
        MetadataService.get_email_by_party_id("test@example.com", "track1", "doc1", "p1")
    assert exc_info.value.status_code == 404
    assert "Party ID" in exc_info.value.detail

def make_valid_doc_data():
    return DocumentRequest(
        document_id="doc123",
        fields=[
            Field(
                id="f1",
                type="text",
                x=10,
                y=20,
                width=100,
                height=20,
                page=1,
                color="#000000",
                style="normal",
                partyId="p1",
                options=[],
                value="v1"
            )
        ],
        email_response=[
            EmailResponse(
                email="response@example.com",
                status="sent",
                email_subject="Subject",
                email_body="Body"
            )
        ],
        validityDate="2025-07-30",
        remainder=1,
        pdfSize=PdfSize(pdfWidth=210, pdfHeight=297),
        parties=[
            {
                "id": "p1",
                "email": "p1@example.com",
                "name": "Party One",
                "color": "#FF0000",
                "priority": 1
            }
        ],
        client_info={
            "ip": "127.0.0.1",
            "city": "TestCity",
            "region": "TestRegion",
            "country": "TestCountry",
            "timezone": "UTC",
            "timestamp": "2025-08-13T00:00:00Z",
            "browser": "Chrome",
            "os": "Windows",
            "device": "Desktop"
        },
        holder=Holder(
            name="Holder Name",
            email="holder@example.com",
            address=Address(
                address_line_1="123 Test St",
                address_line_2="Apt 4",
                city="TestCity",
                state="TestState",
                zipcode="12345",
                country="TestCountry"
            )
        )
    )

def test_generate_document_metadata_success():
    doc_data = make_valid_doc_data()
    parties_status = [{"id": "p1", "status": "pending"}]
    tracking_id = "track123"
    email = "test@example.com"
    metadata = MetadataService.generate_document_metadata(email, doc_data, parties_status, tracking_id)
    assert metadata["tracking_id"] == tracking_id
    assert metadata["document_id"] == doc_data.document_id
    assert metadata["parties"] == parties_status
    assert metadata["pdfSize"] == {"pdfWidth": 210, "pdfHeight": 297}

def test_generate_document_metadata_failure():
    doc_data = None  # Invalid doc_data to trigger error
    email = "test@example.com"
    with pytest.raises(HTTPException) as exc_info:
        MetadataService.generate_document_metadata(email, doc_data, [], "track123")
    assert exc_info.value.status_code == 500

@patch("repositories.s3_repo.load_meta_s3", side_effect=Exception("Other S3 error"))
@patch("app.services.metadata_service.s3_client")
def test_load_metadata_from_s3_other_exception(mock_s3_client, _):
    class NotNoSuchKey(Exception):
        pass
    mock_s3_client.exceptions.NoSuchKey = type("FakeNoSuchKey", (Exception,), {})
    with pytest.raises(Exception) as exc_info:
        MetadataService.load_metadata_from_s3("test@example.com", "track123", "doc123")
    assert "Other S3 error" in str(exc_info.value)

@patch("app.services.metadata_service.MetadataService.get_metadata", return_value=None)
def test_get_email_by_party_id_metadata_none(mock_get_metadata):
    with pytest.raises(HTTPException) as exc_info:
        MetadataService.get_email_by_party_id("test@example.com", "track1", "doc1", "p1")
    assert exc_info.value.status_code == 404
    assert "Tracking metadata not found" in exc_info.value.detail

@patch("app.services.metadata_service.MetadataService.get_metadata", return_value={})
def test_get_email_by_party_id_metadata_no_parties(mock_get_metadata):
    with pytest.raises(HTTPException) as exc_info:
        MetadataService.get_email_by_party_id("test@example.com", "track1", "doc1", "p1")
    assert exc_info.value.status_code == 404
    assert "Tracking metadata not found" in exc_info.value.detail

@patch("app.services.metadata_service.MetadataService.get_metadata", side_effect=Exception("fail"))
def test_get_email_by_party_id_get_metadata_exception(mock_get_metadata):
    with pytest.raises(HTTPException) as exc_info:
        MetadataService.get_email_by_party_id("test@example.com", "track1", "doc1", "p1")
    assert exc_info.value.status_code == 500

def make_valid_doc_data_full():
    return DocumentRequest(
        document_id="doc123",
        fields=[
            Field(
                id="f1",
                type="text",
                x=10,
                y=20,
                width=100,
                height=20,
                page=1,
                color="#000000",
                style="normal",
                partyId="p1",
                options=[],
                value="v1"
            )
        ],
        email_response=[
            EmailResponse(
                email="response@example.com",
                status="sent",
                email_subject="Subject",
                email_body="Body"
            )
        ],
        validityDate="2025-07-30",
        remainder=1,
        pdfSize=PdfSize(pdfWidth=210, pdfHeight=297),
        parties=[
            {
                "id": "p1",
                "email": "p1@example.com",
                "name": "Party One",
                "color": "#FF0000",
                "priority": 1
            }
        ],
        client_info={
            "ip": "127.0.0.1",
            "city": "TestCity",
            "region": "TestRegion",
            "country": "TestCountry",
            "timezone": "UTC",
            "timestamp": "2025-08-13T00:00:00Z",
            "browser": "Chrome",
            "os": "Windows",
            "device": "Desktop"
        },
        holder=Holder(
            name="Holder Name",
            email="holder@example.com",
            address=Address(
                address_line_1="123 Test St",
                address_line_2="Apt 4",
                city="TestCity",
                state="TestState",
                zipcode="12345",
                country="TestCountry"
            )
        )
    )

def test_generate_document_metadata_success_full():
    doc_data = make_valid_doc_data_full()
    parties_status = [{"id": "p1", "status": "pending"}]
    tracking_id = "track123"
    email = "test@example.com"
    metadata = MetadataService.generate_document_metadata(email, doc_data, parties_status, tracking_id)
    assert metadata["tracking_id"] == tracking_id
    assert metadata["document_id"] == doc_data.document_id
    assert metadata["parties"] == parties_status
    assert metadata["pdfSize"] == {"pdfWidth": 210, "pdfHeight": 297}
    assert metadata["fields"][0]["id"] == "f1"
    # Fix: Assert on keys that actually exist
    assert metadata["email_response"][0]["email_subject"] == "Subject"
    assert metadata["email_response"][0]["email_body"] == "Body"
    
def test_generate_document_metadata_missing_party_fields():
    doc_data = make_valid_doc_data_full()
    # Remove required fields from party
    doc_data.parties = [{"id": "p1", "email": "p1@example.com"}]
    email = "test@example.com"
    # Expect ValidationError from Pydantic
    with pytest.raises(ValidationError):
        DocumentRequest(
            document_id=doc_data.document_id,
            fields=doc_data.fields,
            email_response=doc_data.email_response,
            validityDate=doc_data.validityDate,
            remainder=doc_data.remainder,
            pdfSize=doc_data.pdfSize,
            parties=doc_data.parties,
            client_info=doc_data.client_info,
            holder=doc_data.holder
        )

def test_generate_document_metadata_missing_field_fields():
    doc_data = make_valid_doc_data_full()
    # Remove required fields from field
    doc_data.fields = [{"field_id": "f1", "value": "v1"}]
    email = "test@example.com"
    with pytest.raises(Exception):
        MetadataService.generate_document_metadata(email, doc_data, [], "track123")

def test_generate_document_metadata_missing_email_response_fields():
    doc_data = make_valid_doc_data_full()
    # Remove required fields from email_response
    doc_data.email_response = [{"email": "response@example.com", "status": "sent"}]
    email = "test@example.com"
    with pytest.raises(Exception):
        MetadataService.generate_document_metadata(email, doc_data, [], "track123")

def test_generate_document_metadata_missing_holder():
    doc_data = make_valid_doc_data_full()
    doc_data.holder = None
    email = "test@example.com"
    metadata = MetadataService.generate_document_metadata(email, doc_data, [], "track123")
    assert metadata["holder"] == {}

def test_generate_document_metadata_missing_pdf_size():
    doc_data = make_valid_doc_data_full()
    doc_data.pdfSize = None
    email = "test@example.com"
    metadata = MetadataService.generate_document_metadata(email, doc_data, [], "track123")
    assert metadata["pdfSize"] == {}

def test_generate_document_metadata_empty_fields():
    doc_data = make_valid_doc_data_full()
    doc_data.fields = []
    email = "test@example.com"
    metadata = MetadataService.generate_document_metadata(email, doc_data, [], "track123")
    assert metadata["fields"] == []

def test_generate_document_metadata_empty_email_response():
    doc_data = make_valid_doc_data_full()
    doc_data.email_response = []
    email = "test@example.com"
    metadata = MetadataService.generate_document_metadata(email, doc_data, [], "track123")
    assert metadata["email_response"] == []

def test_generate_document_metadata_empty_parties_full():
    doc_data = make_valid_doc_data_full()
    doc_data.parties = []
    email = "test@example.com"
    metadata = MetadataService.generate_document_metadata(email, doc_data, [], "track123")
    assert metadata["parties"] == []

def test_generate_document_metadata_none_validity_date():
    doc_data = make_valid_doc_data_full()
    doc_data.validityDate = None
    email = "test@example.com"
    metadata = MetadataService.generate_document_metadata(email, doc_data, [], "track123")
    assert metadata["validityDate"] is None

def test_generate_document_metadata_none_remainder():
    doc_data = make_valid_doc_data_full()
    doc_data.remainder = None
    email = "test@example.com"
    metadata = MetadataService.generate_document_metadata(email, doc_data, [], "track123")