from io import BytesIO
from typing import Optional, List

from PyPDF2 import PdfMerger
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Response, UploadFile, File, Form
from fastapi import Depends
from starlette.responses import StreamingResponse

from app.schemas.tracking_schemas import DocumentRequest, OTPVerification, SignField, LogActionRequest, \
    DocumentFieldRequest, DocumentResendRequest, OTPSend, MultiPartyUpdateRequest
from app.services.audit_service import DocumentTrackingManager, document_tracking_manager
from app.services.global_audit_service import GlobalAuditService
from app.services.metadata_service import MetadataService
from app.services.otp_service import OtpService
from app.services.pdf_converter import AttachmentConverter
from app.services.pdf_service import PDFSigner, PDFGenerator
from app.services.security_service import AESCipher, EncryptionService
from app.services.signature_service import SignatureHandler
from app.services.tracking_service import TrackingService
from app.threadsafe.redis_lock import with_redis_lock
from auth_app.app.api.routes.deps import dynamic_permission_check, get_email_from_token, get_current_user, \
    get_user_email_from_token, get_role_from_token
from auth_app.app.aspects.subscription_guard import enforce_send_document_policy
from auth_app.app.model.UserModel import FolderAssignment
from config import config
from database.db_config import s3_client, S3_user
from database.redis_db import redis_client
from repositories.s3_repo import get_document_details, save_defaults_fields, load_tracking_metadata_by_tracking_id, \
    s3_upload_bytes, _list_objects, s3_download_bytes, update_parties_tracking
from utils.logger import logger

router = APIRouter()

@router.get("/documents/merged-pdf", dependencies=[Depends(dynamic_permission_check)])
async def get_merged_pdf(
    document_id: str,
    tracking_id: str,
    email: str = Depends(get_email_from_token),
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    # List signed documents from the correct folder
    s3_prefix = f"{email}/signed/{document_id}/{tracking_id}/"
    object_keys = _list_objects(s3_prefix)

    if not object_keys:
        raise HTTPException(status_code=404, detail="No signed documents found.")

    merger = PdfMerger()

    for key in object_keys:
        try:
            encrypted_file = s3_download_bytes(key)
            encryption_service = EncryptionService()
            encryption_email = await encryption_service.resolve_encryption_email(email)
            cipher = AESCipher(encryption_email)
            decrypted = cipher.decrypt(encrypted_file)
            pdf_bytes = AttachmentConverter.convert_to_pdf_if_needed(decrypted, key.split("/")[-1])
            merger.append(BytesIO(pdf_bytes))
        except Exception as e:
            logger.error(f"Failed to merge key {key}: {e}")
            continue

    output_stream = BytesIO()
    merger.write(output_stream)
    merger.close()
    output_stream.seek(0)

    return StreamingResponse(
        output_stream,
        media_type="application/pdf"
    )


@router.get("/documents/all-status", dependencies=[Depends(dynamic_permission_check)])
async def get_all_document_statuses(email: str = Depends(get_email_from_token)):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return document_tracking_manager.get_all_doc_sts(email)


@router.get("/documents/status", dependencies=[Depends(dynamic_permission_check)])
async def get_document_status(tracking_id: str, document_id: str, email: str = Depends(get_email_from_token)):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return document_tracking_manager.get_doc_status(email, tracking_id=tracking_id, document_id=document_id)


@router.get("/documents/party-status", dependencies=[Depends(dynamic_permission_check)])
async def get_party_document_status(tracking_id: str, document_id: str, party_id: str,
                              email: str = Depends(get_email_from_token)):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    metadata, party = MetadataService.get_party_meta(email, document_id, party_id, tracking_id)
    return document_tracking_manager.get_party_doc_sts(document_id, metadata, party, party_id, tracking_id)

@router.post("/documents/resend", dependencies=[Depends(dynamic_permission_check)])
async def resend_document_link(data: DocumentResendRequest, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token),
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return await SignatureHandler.initiate_resend(data=data, email= email, user_email=user_email)


@router.post("/documents/send-otp", dependencies=[Depends(dynamic_permission_check)])
async def send_otp_to_party(data: OTPSend, email: str = Depends(get_email_from_token)):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return OtpService.send_otp_party(email, data.party_id, data.tracking_id, data.document_id)


@router.post("/documents/verify-otp", dependencies=[Depends(dynamic_permission_check)])
async def verify_otp_api(data: OTPVerification, email: str = Depends(get_email_from_token)):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return await OtpService.verify_otp_for_party(email, data)

@router.get("/documents/signed-pdf", dependencies=[Depends(dynamic_permission_check)])
async def get_signed_pdf(tracking_id: str,document_id: str,email: str = Depends(get_email_from_token)):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    pdfSigner = PDFSigner()
    return await pdfSigner.get_signed_file(email, tracking_id, document_id)

@router.get("/documents/signed-package", dependencies=[Depends(dynamic_permission_check)])
async def download_signed_document_package(
    document_id: str,
    tracking_id: str,
    email: str = Depends(get_email_from_token)
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return await PDFGenerator.get_signed_package(email, tracking_id, document_id)


@router.get("/documents/complete-certificates", response_class=Response, dependencies=[Depends(dynamic_permission_check)])
async def get_completed_certificate(
    document_id: str,
    tracking_id: str,
    email: str = Depends(get_email_from_token)
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    s3_key = f"{email}/certificates/documents/{document_id}/tracking/{tracking_id}.pdf"

    try:
        s3_response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=s3_key)
        file_data = s3_response['Body'].read()

        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        try:
            # Try decrypting
            decrypted_pdf_bytes = cipher.decrypt(file_data)
        except Exception:
            # If decryption fails, assume it's not encrypted
            decrypted_pdf_bytes = file_data

        filename = f"certificate_{tracking_id}.pdf"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}"
        }
        return Response(content=decrypted_pdf_bytes, media_type="application/pdf", headers=headers)

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=404, detail="Completed certificate not found in S3")
        raise HTTPException(status_code=500, detail="Error retrieving certificate from S3")

@router.post("/documents/log-action", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="log_action:{tracking_id}", ttl=10)
async def log_action_api(
    data: LogActionRequest,
    email: str = Depends(get_email_from_token)
, user_email: str = Depends(get_user_email_from_token)
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return await document_tracking_manager.log_action_cancel(data, data.client_info, email, user_email)


@router.get("/documents/trackings-status", dependencies=[Depends(dynamic_permission_check)])
async def get_all_tracking_ids_by_status(
    email: str = Depends(get_email_from_token),
    role: str = Depends(get_role_from_token),
    user_email: str = Depends(get_user_email_from_token)
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    trackingService = TrackingService(email)

    if role != "admin":
        user_json_key = f"{email}/roles/{role}.json"
        if not S3_user.exists(user_json_key):
            raise HTTPException(status_code=404, detail="No folder assignment found.")
        user_data = S3_user.read_json(user_json_key)
        assignment = FolderAssignment(**user_data)
        logger.info(assignment)

    return trackingService.get_all_tracking_ids_status(role)


@router.get("/documents/tracking-ids/", dependencies=[Depends(dynamic_permission_check)])
async def get_tracking_ids(document_id: str, email: str = Depends(get_email_from_token)):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return get_document_details(email, document_id)


@router.post("/documents/{document_id}/defaults-fields", dependencies=[Depends(dynamic_permission_check)])
async def save_default_fields(payload: DocumentFieldRequest,email: str = Depends(get_email_from_token)):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return await save_defaults_fields(email, payload)

@router.get("/documents/{document_id}/audit", summary="Get document audit logs by document ID", dependencies=[Depends(dynamic_permission_check)])
async def get_document_logs_by_id(document_id: str, email: str = Depends(get_email_from_token)):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return GlobalAuditService.get_document_logs_by_id(email, document_id)

@router.post(
    "/documents/send",
    dependencies=[
        Depends(dynamic_permission_check),
        Depends(enforce_send_document_policy)
    ]
)
async def send_document(
    doc: DocumentRequest,
    email: str = Depends(get_email_from_token),
    user_email: str = Depends(get_user_email_from_token),
    store_as_default: bool = False
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    handler = SignatureHandler(email, user_email, doc, store_as_default)
    response = await handler.initiate_signature_flow()
    return response

@router.put(
    "/documents/update",
    dependencies=[Depends(dynamic_permission_check)]
)
async def update_parties(
    payload: MultiPartyUpdateRequest,
    email: str = Depends(get_email_from_token)
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    try:
        response = update_parties_tracking(
            email=email,
            document_id=payload.document_id,
            tracking_id=payload.tracking_id,
            parties=payload.parties
        )
        return {"msg": "Parties updated successfully", "data": response}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"[update_parties] Failed for doc {payload.document_id}, tracking {payload.tracking_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update parties info")

@router.get("/documents/{tracking_id}", dependencies=[Depends(dynamic_permission_check)])
async def get_tracking_metadata(
    tracking_id: str,
    email: str = Depends(get_email_from_token),
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return load_tracking_metadata_by_tracking_id(email, tracking_id)


# Signature-related endpoints
@router.post("/documents/sign", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="sign:{document_id}:{tracking_id}", ttl=10)
async def sign_field_api(
    data: SignField,
    user_email: str = Depends(get_user_email_from_token),
    email: str = Depends(get_email_from_token)
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    return await SignatureHandler.sign_field(email, user_email, data)


@router.post("/documents/upload-attachment", dependencies=[Depends(dynamic_permission_check)])
async def upload_attachments(
    files: List[UploadFile] = File(...),
    document_id: str = Form(...),
    tracking_id: str = Form(...), email: str = Depends(get_email_from_token)
):
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)
    if not files:
        return {"detail": "No files uploaded."}


    for file in files:
        document_name = file.filename
        s3_key = f"{email}/signed/{document_id}/{tracking_id}/{document_name}"
        file_bytes = await file.read()

        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        encrypted_file = cipher.encrypt(file_bytes)

        s3_upload_bytes(
            encrypted_file,
            s3_key,
            content_type=file.content_type
        )

    return {"detail": f"{len(files)} file(s) uploaded successfully."}

