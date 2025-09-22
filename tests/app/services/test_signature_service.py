import sys
from unittest.mock import MagicMock

# Patch DB and other side-effectful imports before importing the app code
sys.modules['auth_app.app.database.connection'] = MagicMock(
    db=MagicMock(),
    save_document_url=MagicMock(),
    tracker_collection=MagicMock()
)
sys.modules['repositories.s3_repo'] = MagicMock()
sys.modules['utils.drive_client'] = MagicMock()
sys.modules['utils.logger'] = MagicMock()
sys.modules['utils.scheduler_manager'] = MagicMock()
sys.modules['utils.security'] = MagicMock()
sys.modules['app.services.certificate_service'] = MagicMock()
sys.modules['app.services.email_service'] = MagicMock()
sys.modules['app.services.metadata_service'] = MagicMock()
sys.modules['app.services.notification_service'] = MagicMock()
sys.modules['app.services.pdf_form_field_renderer_service'] = MagicMock()
sys.modules['app.services.pdf_service'] = MagicMock()
sys.modules['app.services.tracking_service'] = MagicMock()
sys.modules['app.services.global_audit_service'] = MagicMock()
sys.modules['app.services.audit_service'] = MagicMock()
sys.modules['auth_app.app.utils.security'] = MagicMock()

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.signature_service import SignatureHandler
from fastapi import HTTPException

@pytest.fixture
def doc_data():
    party = MagicMock(id="1", email="party@example.com", name="Party Name")
    doc = MagicMock(
        document_id="doc1",
        parties=[party],
        scheduled_datetime=None,
        client_info=MagicMock(),
        holder=MagicMock(name="Holder", email="holder@example.com"),
        email_response=[],
        cc_emails=[],
        validityDate="2025-12-31",
        remainder=1
    )
    return doc

@pytest.fixture
def handler(doc_data):
    return SignatureHandler(
        email="user@example.com",
        user_email="owner@example.com",
        doc_data=doc_data,
        request=None,
        store_as_default=False
    )

# --- initiate_signature_flow ---

@patch("app.services.signature_service.document_tracking_manager")
@patch("app.services.signature_service.MetadataService")
@patch("app.services.signature_service.SchedulerManager")
@patch("app.services.signature_service.logger")
@pytest.mark.asyncio
async def test_initiate_signature_flow_immediate(mock_logger, mock_scheduler, mock_metadata, mock_tracking, handler):
    handler.initiate_signing_process = AsyncMock()
    result = await handler.initiate_signature_flow()
    assert result["status"] == "sent"
    handler.initiate_signing_process.assert_awaited_once()

@patch("app.services.signature_service.document_tracking_manager")
@patch("app.services.signature_service.MetadataService")
@patch("app.services.signature_service.SchedulerManager.add_job", side_effect=Exception("fail"))
@patch("app.services.signature_service.logger")
@pytest.mark.asyncio
async def test_initiate_signature_flow_scheduled(mock_logger, mock_add_job, mock_metadata, mock_tracking, handler, doc_data):
    doc_data.scheduled_datetime = MagicMock()
    doc_data.scheduled_datetime.__gt__.return_value = True
    handler.doc_data = doc_data
    with pytest.raises(HTTPException) as exc:
        await handler.initiate_signature_flow()
    assert exc.value.status_code == 500
    assert "Failed to schedule signature initiation" in str(exc.value.detail)
    

@patch("app.services.signature_service.document_tracking_manager")
@patch("app.services.signature_service.MetadataService")
@patch("app.services.signature_service.SchedulerManager.add_job", side_effect=Exception("fail"))
@patch("app.services.signature_service.logger")
@pytest.mark.asyncio
async def test_initiate_signature_flow_schedule_error(mock_logger, mock_add_job, mock_metadata, mock_tracking, handler, doc_data):
    doc_data.scheduled_datetime = MagicMock()
    doc_data.scheduled_datetime.__gt__.return_value = True
    handler.doc_data = doc_data
    with pytest.raises(Exception):
        await handler.initiate_signature_flow()

# --- initiate_signing_process ---

@patch("app.services.signature_service.create_signature_token", new_callable=AsyncMock)
@patch("app.services.signature_service.email_service.send_link", new_callable=AsyncMock)
@patch("app.services.signature_service.document_tracking_manager.log_action", new_callable=AsyncMock)
@patch("app.services.signature_service.logger")
@pytest.mark.asyncio
async def test_initiate_signing_process_success(mock_logger, mock_log_action, mock_send_link, mock_create_token, handler):
    mock_create_token.return_value = {"token": "t", "validity_datetime": "now"}
    await handler.initiate_signing_process()
    mock_send_link.assert_awaited_once()
    mock_log_action.assert_awaited_once()

@patch("app.services.signature_service.create_signature_token", new_callable=AsyncMock, side_effect=ValueError("bad config"))
@patch("app.services.signature_service.logger")
@pytest.mark.asyncio
async def test_initiate_signing_process_value_error(mock_logger, mock_create_token, handler):
    with pytest.raises(Exception):
        await handler.initiate_signing_process()

# --- sign_field ---

@patch("app.services.signature_service.MetadataService.get_metadata")
@patch("app.services.signature_service.PDFSigner")
@patch("app.services.signature_service.document_tracking_manager")
@patch("app.services.signature_service.logger")
@pytest.mark.asyncio
async def test_sign_field_success(mock_logger, mock_tracking, mock_pdfsigner, mock_get_metadata):
    data = MagicMock(document_id="doc1", tracking_id="track1", party_id="1", client_info=MagicMock())
    mock_get_metadata.return_value = {"fields": [], "pdfSize": {"pdfWidth": 595, "pdfHeight": 842}}
    mock_pdfsigner.return_value.finalize_party_signing_and_render_pdf = AsyncMock()
    mock_pdfsigner.return_value.render_signed_pdf = AsyncMock(return_value=("b64", "file.pdf"))
    with patch("app.services.signature_service.MetadataService.update_metadata_fields_with_signed_values", return_value=True), \
         patch("app.services.signature_service.document_tracking_manager.validate_party_and_initialize_status", return_value=([], {})), \
         patch("app.services.signature_service.MetadataService.upload_sign_metadata"), \
         patch("app.services.signature_service.SignatureHandler.complete_party_signature", new_callable=AsyncMock), \
         patch("app.services.signature_service.MetadataService.load_metadata_from_s3", return_value={"tracking_status": {"status": "completed"}}), \
         patch("app.services.signature_service.MetadataService.save_metadata_to_s3"):
        result = await SignatureHandler.sign_field("user@example.com", "owner@example.com", data)
        assert result["signed"] is True

@patch("app.services.signature_service.MetadataService.get_metadata", side_effect=FileNotFoundError)
@pytest.mark.asyncio
async def test_sign_field_tracking_not_found(mock_get_metadata):
    data = MagicMock(document_id="doc1", tracking_id="track1", party_id="1", client_info=MagicMock())
    with pytest.raises(Exception):
        await SignatureHandler.sign_field("user@example.com", "owner@example.com", data)

# --- get_parties_signatures_with_type ---

def test_get_parties_signatures_with_type_drawn():
    data = {"fields": [{"type": "signature", "partyId": "1", "style": "drawn", "value": "b64"}]}
    result = SignatureHandler.get_parties_signatures_with_type(data)
    assert result["1"]["b64_signature"] == "b64"

def test_get_parties_signatures_with_type_typed():
    with patch("app.services.signature_service.generate_signature_b64_from_fontname", return_value="typed_b64"):
        data = {"fields": [{"type": "signature", "partyId": "2", "style": "typed", "value": "sig", "font": "Arial"}]}
        result = SignatureHandler.get_parties_signatures_with_type(data)
        assert result["2"]["b64_signature"] == "typed_b64"

def test_get_parties_signatures_with_type_unknown():
    data = {"fields": [{"type": "signature", "partyId": "3", "style": "unknown"}]}
    result = SignatureHandler.get_parties_signatures_with_type(data)
    assert "3" not in result

# --- decode_base64_with_padding ---

def test_decode_base64_with_padding_valid():
    import base64
    s = base64.b64encode(b"hello").decode()
    assert SignatureHandler.decode_base64_with_padding(s) == b"hello"

def test_decode_base64_with_padding_missing_padding():
    s = "aGVsbG8"  # "hello" without padding
    assert SignatureHandler.decode_base64_with_padding(s) == b"hello"

# --- normalize_signed ---

def test_normalize_signed_dict():
    status = {"signed": {"isSigned": True}}
    result = SignatureHandler.normalize_signed(status, "signed")
    assert isinstance(result, list) and result[0]["isSigned"]

def test_normalize_signed_list():
    status = {"signed": [{"isSigned": True}, {"isSigned": False}]}
    result = SignatureHandler.normalize_signed(status, "signed")
    assert len(result) == 2

def test_normalize_signed_invalid():
    status = []
    result = SignatureHandler.normalize_signed(status, "signed")
    assert result == []

def test_normalize_signed_missing():
    status = {"sent": []}
    result = SignatureHandler.normalize_signed(status, "signed")
    assert result == []

# --- check_all_signed ---

@patch("app.services.signature_service.GlobalAuditService")
@patch("app.services.signature_service.load_all_json_from_prefix", return_value=[{"document_id": "doc1", "trackings": {"track1": {}}}])
@patch("app.services.signature_service.store_tracking_status")
@patch("app.services.signature_service.logger")
def test_check_all_signed_all_signed(mock_logger, mock_store, mock_load, mock_audit):
    parties = [{"status": {"signed": {"isSigned": True}}}]
    SignatureHandler.check_all_signed("user@example.com", parties, "doc1", "track1")
    mock_store.assert_called()

@patch("app.services.signature_service.GlobalAuditService")
@patch("app.services.signature_service.load_all_json_from_prefix", side_effect=Exception("fail"))
@patch("app.services.signature_service.logger")
def test_check_all_signed_load_error(mock_logger, mock_load, mock_audit):
    parties = [{"status": {"signed": {"isSigned": True}}}]
    SignatureHandler.check_all_signed("user@example.com", parties, "doc1", "track1")
    mock_logger.warning.assert_called()

# You can add more tests for error/edge cases as needed.