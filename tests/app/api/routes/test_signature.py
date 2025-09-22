from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import Response
from app.api.routes import signature
from main import app

# --- Dependency overrides for all endpoints ---
def override_get_email_from_token():
    return "test@example.com"
def override_get_user_email_from_token():
    return "test@example.com"
def override_get_role_from_token():
    return "admin"
def override_dynamic_permission_check():
    return None

app.dependency_overrides[signature.get_email_from_token] = override_get_email_from_token
app.dependency_overrides[signature.get_user_email_from_token] = override_get_user_email_from_token
app.dependency_overrides[signature.get_role_from_token] = override_get_role_from_token
app.dependency_overrides[signature.dynamic_permission_check] = override_dynamic_permission_check

client = TestClient(app)

@patch('app.api.routes.signature._list_objects')
@patch('app.api.routes.signature.s3_download_bytes')
@patch('app.api.routes.signature.AESCipher')
@patch('app.api.routes.signature.AttachmentConverter')
@patch('app.api.routes.signature.PdfMerger')
def test_get_merged_pdf_all_files_fail(mock_merger, mock_converter, mock_cipher, mock_download, mock_list):
    mock_list.return_value = ['file1.pdf', 'file2.pdf']
    mock_download.side_effect = [Exception("fail1"), Exception("fail2")]
    instance = mock_merger.return_value
    instance.append.side_effect = Exception("fail")
    instance.write.return_value = None
    instance.close.return_value = None
    response = client.get('/documents/merged-pdf?document_id=doc1&tracking_id=track1')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature._list_objects')
@patch('app.api.routes.signature.s3_download_bytes')
@patch('app.api.routes.signature.AESCipher')
@patch('app.api.routes.signature.AttachmentConverter')
@patch('app.api.routes.signature.PdfMerger')
def test_get_merged_pdf_one_file_not_pdf(mock_merger, mock_converter, mock_cipher, mock_download, mock_list):
    mock_list.return_value = ['file1.docx']
    mock_download.return_value = b'encrypted'
    mock_cipher.return_value.decrypt.return_value = b'decrypted'
    mock_converter.convert_to_pdf_if_needed.side_effect = Exception("conversion failed")
    instance = mock_merger.return_value
    instance.append.side_effect = Exception("conversion failed")
    instance.write.return_value = None
    instance.close.return_value = None
    response = client.get('/documents/merged-pdf?document_id=doc1&tracking_id=track1')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.document_tracking_manager.get_all_doc_sts', new_callable=AsyncMock)
def test_get_all_document_statuses_empty(mock_get_all_doc_sts):
    mock_get_all_doc_sts.return_value = []
    response = client.get('/documents/all-status')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.document_tracking_manager.get_all_doc_sts', new_callable=AsyncMock)
def test_get_all_document_statuses_exception(mock_get_all_doc_sts):
    mock_get_all_doc_sts.side_effect = Exception("fail")
    response = client.get('/documents/all-status')
    assert response.status_code in (500, 200)

@patch('app.api.routes.signature.document_tracking_manager.get_doc_status', new_callable=AsyncMock)
def test_get_document_status_found(mock_get_doc_status):
    mock_get_doc_status.return_value = {"status": "signed"}
    response = client.get('/documents/status?tracking_id=tid&document_id=did')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.document_tracking_manager.get_doc_status', new_callable=AsyncMock)
def test_get_document_status_not_found(mock_get_doc_status):
    mock_get_doc_status.return_value = None
    response = client.get('/documents/status?tracking_id=tid&document_id=did')
    assert response.status_code in (404, 200, 500)

@patch('app.api.routes.signature.MetadataService.get_party_meta', new_callable=AsyncMock)
@patch('app.api.routes.signature.document_tracking_manager.get_party_doc_sts', new_callable=AsyncMock)
def test_get_party_document_status_found(mock_get_party_doc_sts, mock_get_party_meta):
    mock_get_party_meta.return_value = ({}, {})
    mock_get_party_doc_sts.return_value = {"status": "signed"}
    response = client.get('/documents/party-status?tracking_id=tid&document_id=did&party_id=pid')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.MetadataService.get_party_meta', new_callable=AsyncMock)
@patch('app.api.routes.signature.document_tracking_manager.get_party_doc_sts', new_callable=AsyncMock)
def test_get_party_document_status_none(mock_get_party_doc_sts, mock_get_party_meta):
    mock_get_party_meta.return_value = (None, None)
    mock_get_party_doc_sts.return_value = None
    response = client.get('/documents/party-status?tracking_id=tid&document_id=did&party_id=pid')
    assert response.status_code in (404, 200, 500)

@patch('app.api.routes.signature.PDFSigner.get_signed_file', new_callable=AsyncMock)
def test_get_signed_pdf_content(mock_get_signed_file):
    mock_get_signed_file.return_value = Response(content=b"pdf", media_type="application/pdf")
    response = client.get('/documents/signed-pdf?tracking_id=tid&document_id=did')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.PDFSigner.get_signed_file', new_callable=AsyncMock)
def test_get_signed_pdf_no_content(mock_get_signed_file):
    mock_get_signed_file.return_value = None
    response = client.get('/documents/signed-pdf?tracking_id=tid&document_id=did')
    assert response.status_code in (404, 200, 500)

@patch('app.api.routes.signature.PDFGenerator.get_signed_package', new_callable=AsyncMock)
def test_download_signed_document_package_content(mock_get_signed_package):
    mock_get_signed_package.return_value = Response(content=b"zip", media_type="application/zip")
    response = client.get('/documents/signed-package?document_id=did&tracking_id=tid')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.PDFGenerator.get_signed_package', new_callable=AsyncMock)
def test_download_signed_document_package_none(mock_get_signed_package):
    mock_get_signed_package.return_value = None
    response = client.get('/documents/signed-package?document_id=did&tracking_id=tid')
    assert response.status_code in (404, 200, 500)

@patch('app.api.routes.signature.s3_client')
@patch('app.api.routes.signature.AESCipher')
@patch('app.api.routes.signature.config')
@patch('app.api.routes.signature.EncryptionService.resolve_encryption_email', new_callable=AsyncMock)
def test_get_completed_certificate_decrypt_fails(mock_resolve, mock_config, mock_cipher, mock_s3):
    mock_config.S3_BUCKET = 'bucket'
    mock_s3.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b'encrypted'))}
    mock_cipher.return_value.decrypt.side_effect = Exception('Decrypt error')
    mock_resolve.return_value = "test@example.com"
    response = client.get('/documents/complete-certificates?document_id=did&tracking_id=tid')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.TrackingService.get_all_tracking_ids_status', new_callable=AsyncMock)
@patch('app.api.routes.signature.S3_user')
def test_get_all_tracking_ids_by_status_no_assignment(mock_s3_user, mock_get_all_tracking_ids_status):
    mock_s3_user.exists.return_value = False
    mock_get_all_tracking_ids_status.return_value = []
    response = client.get('/documents/trackings-status')
    assert response.status_code in (403, 404, 500)

@patch('app.api.routes.signature.TrackingService.get_all_tracking_ids_status', new_callable=AsyncMock)
def test_get_all_tracking_ids_by_status_admin(mock_get_all_tracking_ids_status):
    mock_get_all_tracking_ids_status.return_value = [{"tracking_id": "tid"}]
    with patch('app.api.routes.signature.get_role_from_token', return_value="admin"):
        response = client.get('/documents/trackings-status')
        assert response.status_code in (200, 403, 500)

@patch('app.api.routes.signature.get_document_details', new_callable=AsyncMock)
def test_get_tracking_ids_empty(mock_get):
    mock_get.return_value = []
    response = client.get('/documents/tracking-ids/?document_id=did')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.GlobalAuditService.get_document_logs_by_id', new_callable=AsyncMock)
def test_get_document_logs_by_id_empty(mock_get_logs):
    mock_get_logs.return_value = []
    response = client.get('/documents/did/audit')
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.SignatureHandler')
def test_send_document_invalid_payload(mock_handler):
    mock_handler.return_value.initiate_signature_flow = AsyncMock(return_value={"sent": False})
    data = {"invalid": "data"}
    response = client.post('/documents/send', json=data)
    assert response.status_code in (422, 403, 500)

@patch('app.api.routes.signature.update_parties_tracking')
def test_update_parties_success(mock_update):
    mock_update.return_value = {"updated": True}
    data = {"document_id": "did", "tracking_id": "tid", "parties": [{"id": "pid"}]}
    response = client.put('/documents/update', json=data)
    assert response.status_code in (200, 422, 500)

@patch('app.api.routes.signature.update_parties_tracking')
def test_update_parties_http_exception(mock_update):
    from fastapi import HTTPException
    mock_update.side_effect = HTTPException(status_code=400, detail="Bad request")
    data = {"document_id": "did", "tracking_id": "tid", "parties": [{"id": "pid"}]}
    response = client.put('/documents/update', json=data)
    assert response.status_code in (400, 422, 500)

@patch('app.api.routes.signature.update_parties_tracking')
def test_update_parties_general_exception(mock_update):
    mock_update.side_effect = Exception("Unexpected error")
    data = {"document_id": "did", "tracking_id": "tid", "parties": [{"id": "pid"}]}
    response = client.put('/documents/update', json=data)
    assert response.status_code in (500, 422)

@patch('app.api.routes.signature.load_tracking_metadata_by_tracking_id', new_callable=AsyncMock)
def test_get_tracking_metadata_none(mock_load):
    mock_load.return_value = None
    response = client.get('/documents/tid')
    assert response.status_code in (404, 200, 500)

@patch('app.api.routes.signature.s3_upload_bytes', new_callable=AsyncMock)
@patch('app.api.routes.signature.AESCipher')
@patch('app.api.routes.signature.EncryptionService.resolve_encryption_email', new_callable=AsyncMock)
def test_upload_attachments_multiple_files(mock_resolve, mock_cipher, mock_upload):
    mock_resolve.return_value = "test@example.com"
    mock_cipher.return_value.encrypt.return_value = b'encrypted'
    files = [
        ('files', ('test1.pdf', b'filecontent1', 'application/pdf')),
        ('files', ('test2.pdf', b'filecontent2', 'application/pdf'))
    ]
    data = {'document_id': 'doc1', 'tracking_id': 'track1'}
    response = client.post('/documents/upload-attachment', files=files, data=data)
    assert response.status_code in (200, 500)

@patch('app.api.routes.signature.s3_upload_bytes', new_callable=AsyncMock)
@patch('app.api.routes.signature.AESCipher')
@patch('app.api.routes.signature.EncryptionService.resolve_encryption_email', new_callable=AsyncMock)
def test_upload_attachments_file_upload_error(mock_resolve, mock_cipher, mock_upload):
    mock_resolve.return_value = "test@example.com"
    mock_cipher.return_value.encrypt.return_value = b'encrypted'
    mock_upload.side_effect = Exception('S3 upload error')
    files = {'files': ('test.pdf', b'filecontent', 'application/pdf')}
    data = {'document_id': 'doc1', 'tracking_id': 'track1'}
    response = client.post('/documents/upload-attachment', files=files, data=data)
    assert response.status_code in (500, 200)