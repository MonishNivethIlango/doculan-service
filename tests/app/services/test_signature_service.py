# Mock DB module before importing anything that uses it
import sys
from unittest.mock import MagicMock
sys.modules["auth_app.app.database.connection"] = MagicMock()

import pytest
import asyncio
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
from app.services.signature_service import SignatureHandler
from app.schemas.tracking_schemas import DocumentRequest, Party
from app.schemas.form_schema import EmailResponse

@pytest.fixture
def sample_doc_data():
    from app.schemas.tracking_schemas import ClientInfo, Holder, Address, PdfSize
    return DocumentRequest(
        document_id="doc123",
        parties=[
            Party(
                id="party1",
                email="signer@example.com",
                name="Signer One",
                color="#000000",
                priority=1
            )
        ],
        validityDate="2025-12-31",
        remainder=5,
        pdfSize=PdfSize(pdfWidth=595, pdfHeight=842),
        fields=[],
        email_response=[
            {
                "email_subject": "Please Sign Document",
                "email_body": "Hi, please sign the attached document."
            }
        ],
        client_info=ClientInfo(
            ip="127.0.0.1",
            city="TestCity",
            region="TestRegion",
            country="TestCountry",
            timezone="UTC",
            timestamp="2024-01-01T00:00:00Z",
            browser="Chrome",
            os="Windows",
            device="Desktop"
        ),
        holder=Holder(
            name="Holder Name",
            email="holder@example.com",
            address=Address(
                address_line_1="123 Test St",
                address_line_2=None,
                city="TestCity",
                country="TestCountry",
                state="TestState",
                zipcode="12345"
            )
        )
    )

import pytest

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action")
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process")
async def test_initiate_signature_flow_success(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=sample_doc_data,
        request=MagicMock()
    )

    mock_initialize_status.return_value = {"party1": {"status": {}}}
    mock_generate_metadata.return_value = {"meta": "data"}

    result = await handler.initiate_signature_flow()

    assert result == {"tracking_id": handler.tracking_id, "status": "sent"}
    mock_initialize_status.assert_called_once_with(sample_doc_data)
    mock_generate_metadata.assert_called_once()
    mock_upload_metadata.assert_called_once()
    mock_log_action.assert_called_once()
    mock_initiate_signing_process.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status", side_effect=Exception("init fail"))
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action")
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process")
async def test_initiate_signature_flow_init_status_fail(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=sample_doc_data,
        request=MagicMock()
    )
    with pytest.raises(Exception) as exc:
        await handler.initiate_signature_flow()
    assert hasattr(exc.value, 'status_code') and exc.value.status_code == 500
    assert hasattr(exc.value, 'detail') and exc.value.detail == "Failed to initiate signature flow."

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata", side_effect=Exception("meta fail"))
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action")
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process")
async def test_initiate_signature_flow_metadata_fail(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=sample_doc_data,
        request=MagicMock()
    )
    with pytest.raises(Exception) as exc:
        await handler.initiate_signature_flow()
    assert hasattr(exc.value, 'status_code') and exc.value.status_code == 500
    assert hasattr(exc.value, 'detail') and exc.value.detail == "Failed to initiate signature flow."

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata", side_effect=Exception("upload fail"))
@patch("app.services.signature_service.GlobalAuditService.log_document_action")
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process")
async def test_initiate_signature_flow_upload_fail(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=sample_doc_data,
        request=MagicMock()
    )
    with pytest.raises(Exception) as exc:
        await handler.initiate_signature_flow()
    assert hasattr(exc.value, 'status_code') and exc.value.status_code == 500
    assert hasattr(exc.value, 'detail') and exc.value.detail == "Failed to initiate signature flow."

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action", side_effect=Exception("audit fail"))
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process")
async def test_initiate_signature_flow_audit_fail(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=sample_doc_data,
        request=MagicMock()
    )
    with pytest.raises(Exception) as exc:
        await handler.initiate_signature_flow()
    assert hasattr(exc.value, 'status_code') and exc.value.status_code == 500
    assert hasattr(exc.value, 'detail') and exc.value.detail == "Failed to initiate signature flow."

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action")
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process", side_effect=Exception("sign fail"))
async def test_initiate_signature_flow_signing_fail(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=sample_doc_data,
        request=MagicMock()
    )
    with pytest.raises(Exception) as exc:
        await handler.initiate_signature_flow()
    assert hasattr(exc.value, 'status_code') and exc.value.status_code == 500
    assert hasattr(exc.value, 'detail') and exc.value.detail == "Failed to initiate signature flow."

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action")
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process")
async def test_initiate_signature_flow_invalid_doc_data(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status
):
    from app.schemas.tracking_schemas import DocumentRequest, ClientInfo, Holder, Address, PdfSize
    doc_data = DocumentRequest(
        document_id="doc123",
        parties=[],
        validityDate="2025-12-31",
        remainder=5,
        pdfSize=PdfSize(pdfWidth=595, pdfHeight=842),
        fields=[],
        email_response=[],
        client_info=ClientInfo(
            ip="127.0.0.1",
            city="TestCity",
            region="TestRegion",
            country="TestCountry",
            timezone="UTC",
            timestamp="2024-01-01T00:00:00Z",
            browser="Chrome",
            os="Windows",
            device="Desktop"
        ),
        holder=Holder(
            name="Holder Name",
            email="holder@example.com",
            address=Address(
                address_line_1="123 Test St",
                address_line_2=None,
                city="TestCity",
                country="TestCountry",
                state="TestState",
                zipcode="12345"
            )
        )
    )
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=doc_data,
        request=MagicMock()
    )
    result = await handler.initiate_signature_flow()
    assert result["status"] == "sent"

def test_initiate_signature_flow_invalid_party_email():
    from app.schemas.tracking_schemas import ClientInfo, Holder, Address, PdfSize, Party
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DocumentRequest(
            document_id="doc123",
            parties=[
                Party(
                    id="party1",
                    email="not-an-email",
                    name="Signer One",
                    color="#000000",
                    priority=1
                )
            ],
            validityDate="2025-12-31",
            remainder=5,
            pdfSize=PdfSize(pdfWidth=595, pdfHeight=842),
            fields=[],
            email_response=[],
            client_info=ClientInfo(
                ip="127.0.0.1",
                city="TestCity",
                region="TestRegion",
                country="TestCountry",
                timezone="UTC",
                timestamp="2024-01-01T00:00:00Z",
                browser="Chrome",
                os="Windows",
                device="Desktop"
            ),
            holder=Holder(
                name="Holder Name",
                email="holder@example.com",
                address=Address(
                    address_line_1="123 Test St",
                    address_line_2=None,
                    city="TestCity",
                    country="TestCountry",
                    state="TestState",
                    zipcode="12345"
                )
            )
        )

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action")
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process")
async def test_initiate_signature_flow_missing_holder(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    doc_data = sample_doc_data.copy(update={"holder": None})
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=doc_data,
        request=MagicMock()
    )
    mock_initialize_status.return_value = {"party1": {"status": {}}}
    mock_generate_metadata.return_value = {"meta": "data"}
    result = await handler.initiate_signature_flow()
    assert result == {"tracking_id": handler.tracking_id, "status": "sent"}

def test_initiate_signature_flow_missing_client_info():
    from app.schemas.tracking_schemas import Holder, Address, PdfSize, Party
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DocumentRequest(
            document_id="doc123",
            parties=[
                Party(
                    id="party1",
                    email="signer@example.com",
                    name="Signer One",
                    color="#000000",
                    priority=1
                )
            ],
            validityDate="2025-12-31",
            remainder=5,
            pdfSize=PdfSize(pdfWidth=595, pdfHeight=842),
            fields=[],
            email_response=[],
            client_info=None,
            holder=Holder(
                name="Holder Name",
                email="holder@example.com",
                address=Address(
                    address_line_1="123 Test St",
                    address_line_2=None,
                    city="TestCity",
                    country="TestCountry",
                    state="TestState",
                    zipcode="12345"
                )
            )
        )

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action")
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process")
async def test_initiate_signature_flow_multiple_parties(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    from app.schemas.tracking_schemas import Party
    doc_data = sample_doc_data.copy(update={
        "parties": [
            Party(
                id="party1",
                email="signer1@example.com",
                name="Signer One",
                color="#000000",
                priority=1
            ),
            Party(
                id="party2",
                email="signer2@example.com",
                name="Signer Two",
                color="#111111",
                priority=2
            )
        ]
    })
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=doc_data,
        request=MagicMock()
    )
    mock_initialize_status.return_value = {"party1": {"status": {}}, "party2": {"status": {}}}
    mock_generate_metadata.return_value = {"meta": "data"}
    result = await handler.initiate_signature_flow()
    assert result == {"tracking_id": handler.tracking_id, "status": "sent"}

def test_initiate_signature_flow_invalid_pdf_size():
    from app.schemas.tracking_schemas import ClientInfo, Holder, Address, Party
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DocumentRequest(
            document_id="doc123",
            parties=[
                Party(
                    id="party1",
                    email="signer@example.com",
                    name="Signer One",
                    color="#000000",
                    priority=1
                )
            ],
            validityDate="2025-12-31",
            remainder=5,
            pdfSize=None,
            fields=[],
            email_response=[],
            client_info=ClientInfo(
                ip="127.0.0.1",
                city="TestCity",
                region="TestRegion",
                country="TestCountry",
                timezone="UTC",
                timestamp="2024-01-01T00:00:00Z",
                browser="Chrome",
                os="Windows",
                device="Desktop"
            ),
            holder=Holder(
                name="Holder Name",
                email="holder@example.com",
                address=Address(
                    address_line_1="123 Test St",
                    address_line_2=None,
                    city="TestCity",
                    country="TestCountry",
                    state="TestState",
                    zipcode="12345"
                )
            )
        )

def test_initiate_signature_flow_invalid_email_response():
    from app.schemas.tracking_schemas import ClientInfo, Holder, Address, PdfSize, Party
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DocumentRequest(
            document_id="doc123",
            parties=[
                Party(
                    id="party1",
                    email="signer@example.com",
                    name="Signer One",
                    color="#000000",
                    priority=1
                )
            ],
            validityDate="2025-12-31",
            remainder=5,
            pdfSize=PdfSize(pdfWidth=595, pdfHeight=842),
            fields=[],
            email_response=[{"foo": "bar"}],
            client_info=ClientInfo(
                ip="127.0.0.1",
                city="TestCity",
                region="TestRegion",
                country="TestCountry",
                timezone="UTC",
                timestamp="2024-01-01T00:00:00Z",
                browser="Chrome",
                os="Windows",
                device="Desktop"
            ),
            holder=Holder(
                name="Holder Name",
                email="holder@example.com",
                address=Address(
                    address_line_1="123 Test St",
                    address_line_2=None,
                    city="TestCity",
                    country="TestCountry",
                    state="TestState",
                    zipcode="12345"
                )
            )
        )

import pytest
import asyncio

@pytest.mark.asyncio
async def test_initiate_signature_flow_invalid_doc_data_type():
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data="not_a_doc_request",
        request=MagicMock()
    )
    with pytest.raises(Exception):
        await handler.initiate_signature_flow()

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action")
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process", side_effect=asyncio.TimeoutError("timeout"))
async def test_initiate_signature_flow_async_exception(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=sample_doc_data,
        request=MagicMock()
    )
    with pytest.raises(Exception) as exc:
        await handler.initiate_signature_flow()
    assert hasattr(exc.value, 'status_code') and exc.value.status_code == 500
    assert hasattr(exc.value, 'detail') and exc.value.detail == "Failed to initiate signature flow."

@pytest.mark.asyncio
@patch("app.services.signature_service.DocumentTrackingManager.initialize_parties_status")
@patch("app.services.signature_service.MetadataService.generate_document_metadata")
@patch("app.services.signature_service.MetadataService.upload_metadata")
@patch("app.services.signature_service.GlobalAuditService.log_document_action", side_effect=HTTPException(status_code=404, detail="Not found"))
@patch("app.services.signature_service.SignatureHandler.initiate_signing_process")
async def test_initiate_signature_flow_dependency_http_exception(
    mock_initiate_signing_process,
    mock_log_action,
    mock_upload_metadata,
    mock_generate_metadata,
    mock_initialize_status,
    sample_doc_data
):
    handler = SignatureHandler(
        email="sender@example.com",
        doc_data=sample_doc_data,
        request=MagicMock()
    )
    with pytest.raises(Exception) as exc:
        await handler.initiate_signature_flow()
    assert hasattr(exc.value, 'status_code') and exc.value.status_code == 500
    assert hasattr(exc.value, 'detail') and exc.value.detail == "Failed to initiate signature flow."