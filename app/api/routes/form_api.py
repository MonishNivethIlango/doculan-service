import json
import logging
import uuid
from typing import List
from fastapi import APIRouter, Depends, Request, Query, UploadFile, File, Form
from starlette import status
import io
import zipfile
from fastapi import Response
from app.model.form_model import FormModel
from app.schemas.form_schema import RegistrationForm, FormRequest, FormSubmissionRequest, OtpFormVerification, \
    ResendFormRequest, OtpFormSend, FormCancelled
from app.services.FormService import FormService
from app.services.pdf_converter import AttachmentConverter
from app.services.security_service import AESCipher, EncryptionService
from app.threadsafe.redis_lock import with_redis_lock
from auth_app.app.api.routes.deps import dynamic_permission_check, get_email_from_token, get_current_user, \
    get_user_email_from_token
from config import config
from database.db_config import s3_client
from database.redis_db import redis_client
from app.services.otp_service import OtpService
from repositories.s3_repo import s3_download_bytes

logger = logging.getLogger(__name__)
router = APIRouter()




@router.post("/forms/", dependencies=[Depends(dynamic_permission_check)])
async def create_form(form: RegistrationForm, email: str = Depends(get_email_from_token), current_user: dict = Depends(get_current_user), user_email: str = Depends(get_user_email_from_token)):
    formService = FormService()
    form_id = str(uuid.uuid4())
    formService.create_form(form_id, form.dict(), email, current_user, user_email)
    return {"message": "Form saved successfully", "form_id": form_id}


@router.get("/forms/{form_id}", dependencies=[Depends(dynamic_permission_check)])
async def get_form(form_id: str, email: str = Depends(get_email_from_token)):
    formService = FormService()
    form_data = formService.get_form(form_id, email)
    if not form_data:
        raise HTTPException(status_code=404, detail="Form not found")
    return form_data


@router.get("/forms/", dependencies=[Depends(dynamic_permission_check)])
async def get_all_forms(email: str = Depends(get_email_from_token)):
    formService = FormService()
    forms = formService.get_all_forms(email)
    return {"forms": forms}


@router.put("/forms/{form_id}", dependencies=[Depends(dynamic_permission_check)])
async def update_form(form_id: str, form: RegistrationForm, email: str = Depends(get_email_from_token)):
    formService = FormService()
    if not formService.get_form(form_id, email):
        raise HTTPException(status_code=404, detail="Form not found")
    formService.update_form(form_id, form.dict(), email)
    return {"message": "Form updated successfully"}


@router.delete("/forms/{form_id}", dependencies=[Depends(dynamic_permission_check)])
async def delete_form(form_id: str, email: str = Depends(get_email_from_token)):
    formService = FormService()
    if not formService.get_form(form_id, email):
        raise HTTPException(status_code=404, detail="Form not found")
    formService.delete_form(form_id, email)
    return {"message": "Form deleted successfully"}



@router.post("/forms/send", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="send:{form_id}", ttl=10)
async def send_form(data: FormRequest, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token),
):
    formService = FormService()

    return await formService.send_forms(data, email, user_email)


@router.post("/forms/resend", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="resend:{form_id}:{party_email}", ttl=10)
async def resend_form(data: ResendFormRequest, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token),
):
    formService = FormService()
    return await formService.resend_form(data, data.form_id, data.party_email, email, user_email)


@router.post("/forms/send-otp", dependencies=[Depends(dynamic_permission_check)])
def send_otp_to_party(
data: OtpFormSend,

    email: str = Depends(get_email_from_token)
):
    if not data.party_email:
        raise HTTPException(status_code=400, detail="party_email is required")
    return OtpService.send_form_otp(
        email=email,
        form_id=data.form_id,
        party_email=data.party_email,
    )

@router.post("/forms/verify-otp", dependencies=[Depends(dynamic_permission_check)])
def verify_otp_api(data: OtpFormVerification, request: Request, email: str = Depends(get_email_from_token)):
    return OtpService.verify_form_otp_for_party(email, data, request)


@router.post("/forms/submit", dependencies=[Depends(dynamic_permission_check)])
async def submit_form_values(submission: FormSubmissionRequest, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    formService = FormService()
    return await formService.submit(email, submission, user_email)

@router.post("/forms/{form_id}/cancel", dependencies=[Depends(dynamic_permission_check)])
async def cancel_form_party(
    data: FormCancelled,
    email: str = Depends(get_email_from_token)
):
    FormModel.cancel_form_party(email, data, data.form_id, data.party_email, data.reason)


@router.get(
    "/forms/{form_id}/trackings",
    dependencies=[Depends(dynamic_permission_check)]
)
def get_form_submitted_values(
    form_id: str,
    party_email: str,  # required parameter
    email: str = Depends(get_email_from_token),
):
    return FormService.get_party_submitted_values(email, form_id, party_email)

@router.get("/forms/{form_id}/parties/{party_email}/download", dependencies=[Depends(dynamic_permission_check)])
async def download_pdf(
    form_id: str,
    party_email: str,
    as_attachment: bool = False,
    email: str = Depends(get_email_from_token)
):
    formService = FormService()
    pdf_bytes = await formService.get_pdf_to_s3(email, form_id, party_email)
    content_disposition = (
        f'attachment; filename="form_{form_id}_{party_email}_filled.pdf"'
        if as_attachment else
        'inline; filename="preview.pdf"'
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition}
    )


@router.get("/forms/{form_id}/statuses", dependencies=[Depends(dynamic_permission_check)])
def get_all_statuses(form_id: str, email: str = Depends(get_email_from_token),):
    return FormService.get_all_statuses(email, form_id)


@router.get("/forms/statuses/count", dependencies=[Depends(dynamic_permission_check)])
def get_status_counts(form_id: str = Query(None, description="Form ID to filter. If omitted, counts across all forms."),
    email: str = Depends(get_email_from_token),
):
    return FormService.get_status_counts(email, form_id)



@router.get( "/forms/trackings-status/count", dependencies=[Depends(dynamic_permission_check)])
def get_trackings_status_counts(
    email: str = Depends(get_email_from_token),):
    return FormService.get_trackings_status_counts(email)


@router.get("/forms/{form_id}/trackings/status", dependencies=[Depends(dynamic_permission_check)])
async def get_party_status(
    form_id: str,
    party_email: str,
    email: str = Depends(get_email_from_token),
    form_service: FormService = Depends()
):
    result = await form_service.get_party_status(email, form_id, party_email)
    if not result:
        raise HTTPException(status_code=404, detail="Submission data not found")
    return result

# routes/form_routes.py
@router.get("/forms/trackings/all", dependencies=[Depends(dynamic_permission_check)])
async def get_all_submitted_values_for_user(
    email: str = Depends(get_email_from_token),
    form_service: FormService = Depends()
):
    result = await form_service.get_all_submitted_values(email)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No submitted form values found for the user"
        )
    return {"submissions": result}




from datetime import datetime, timezone


@router.post("/forms/upload-attachments", dependencies=[Depends(dynamic_permission_check)])
async def upload_attachments(
    files: List[UploadFile] = File(...),
    form_id: str = Form(...),
    party_email: str = Form(...),
    email: str = Depends(get_email_from_token)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    try:
        formService = FormService()
        form_data = formService.get_form(form_id, email)
        form_path = form_data.get("formPath", "")

        uploaded_files = []
        for file in files:
            document_id = "form-doc-" + str(uuid.uuid4())
            document_name = file.filename
            s3_key = f"{email}/files/{form_path}/{party_email}/{document_name}"

            # Read and encrypt
            file_bytes = await file.read()
            encryption_service = EncryptionService()
            encryption_email = await encryption_service.resolve_encryption_email(email)
            cipher = AESCipher(encryption_email)
            encrypted_file = cipher.encrypt(file_bytes)

            # Upload file to S3
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=s3_key,
                Body=encrypted_file,
                ContentType=file.content_type,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )

            # Upload metadata
            user_name = FormModel.get_form_party_name(email, form_id, party_email)

            metadata_key = f"{email}/metadata/data/{document_id}.json"
            metadata = {
                "document_id": document_id,
                "fileName": document_name,
                "fileSizeBytes": len(file_bytes),
                "contentType": file.content_type,
                "file_path": s3_key,
                "form_id": form_id,
                "created_by": {"name": user_name, "email": party_email},

            }
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=metadata_key,
                Body=json.dumps(metadata),
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )

            # Update document index
            index_key = f"{email}/index/document_index.json"
            try:
                response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=index_key)
                index_data = json.loads(response['Body'].read().decode('utf-8'))
            except s3_client.exceptions.NoSuchKey:
                index_data = {}
            except Exception as e:
                logger.warning(f"Could not read index: {e}")
                index_data = {}

            last_modified = datetime.now(timezone.utc).isoformat()
            index_data[document_id] = {
                "file_path": s3_key,
                "metadata_path": metadata_key,
                "fileName": document_name,
                "size": len(file_bytes),
                "last_modified": last_modified,
                "form_id": form_id,
                "created_by": {"name": user_name, "email": party_email},
            }
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=index_key,
                Body=json.dumps(index_data),
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )

            uploaded_files.append({
                "document_id": document_id,
                "file_name": document_name,
                "s3_path": s3_key,
                "metadata_key": metadata_key
            })

        return {
            "detail": f"{len(files)} file(s) uploaded successfully.",
            "uploaded": uploaded_files
        }

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")


@router.get("/forms/{form_id}/{party_email}/attachments", dependencies=[Depends(dynamic_permission_check)])
async def download_all_attachments(
    form_id: str,
    party_email: str,
    email: str = Depends(get_email_from_token)
):
    # 1️⃣ Get form data
    form_data = FormService.get_form(form_id, email)
    form_path = form_data.get("formPath")
    form_title = form_data.get("formTitle")
    if not form_path or not form_title:
        raise HTTPException(status_code=404, detail="Form path/title not found")

    prefix = f"{email}/files/{form_path}/{party_email}/"

    # 2️⃣ Get form_user_data.json
    form_user_data = FormModel.get_form_user_data(form_id, email)
    if party_email not in form_user_data:
        raise HTTPException(status_code=404, detail="Party data not found")

    # 3️⃣ Collect uploaded attachment filenames
    file_fields = [
        field for field in form_user_data[party_email]
        if field.get("type") == "file" and field.get("value")
    ]
    filenames = []
    for field in file_fields:
        if isinstance(field["value"], list):
            filenames.extend(field["value"])
        else:
            filenames.append(field["value"])

    # 3.1️⃣ Always add the filled PDF
    filled_pdf_name = f"{form_title}-filled.pdf"
    filenames.append(filled_pdf_name)

    if not filenames:
        raise HTTPException(status_code=404, detail="No attachments found for this party")

    # 4️⃣ Fetch & ZIP only those files
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for filename in filenames:
            key = prefix + filename
            try:
                file_obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
                encrypted_file = file_obj["Body"].read()
                encryption_service = EncryptionService()
                encryption_email = await encryption_service.resolve_encryption_email(email)
                cipher = AESCipher(encryption_email)
                decrypted_file = cipher.decrypt(encrypted_file)
                zipf.writestr(filename, decrypted_file)
            except ClientError as e:
                # skip missing file but continue
                logger.warning(f"File not found in S3: {key} ({str(e)})")
                continue

    if not zip_buffer.getbuffer().nbytes:
        raise HTTPException(status_code=404, detail="No matching files found in S3")

    # 5️⃣ Return ZIP
    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.read(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={form_id}_{party_email}_attachments.zip"
        }
    )


from fastapi import HTTPException, Depends
from fastapi.responses import StreamingResponse
from PyPDF2 import PdfMerger
from botocore.exceptions import ClientError
from io import BytesIO

@router.get("/forms/merged/pdf", dependencies=[Depends(dynamic_permission_check)])
async def get_merged_pdf(
    form_id: str,
    party_email: str,
    email: str = Depends(get_email_from_token),
):
    # 1️⃣ Get form path from form metadata
    form_data = FormService.get_form(form_id, email)
    form_path = form_data.get("formPath")
    formTitle = form_data.get("formTitle")  # ✅ get title to build exclusion filename

    if not form_path:
        raise HTTPException(status_code=404, detail="Form path not found")

    # 2️⃣ List files in the form/party_email folder
    s3_prefix = f"{email}/files/{form_path}/{party_email}/"
    try:
        resp = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=s3_prefix)
        object_keys = [obj["Key"] for obj in resp.get("Contents", [])]
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 error: {str(e)}")

    if not object_keys:
        raise HTTPException(status_code=404, detail="No signed documents found.")

    # 🚫 Exclude the main filled form
    exclude_file = f"{formTitle}-filled.pdf"
    object_keys = [k for k in object_keys if not k.endswith(exclude_file)]

    if not object_keys:
        raise HTTPException(status_code=404, detail="No attachments to merge (all excluded).")

    # 3️⃣ Merge PDFs
    merger = PdfMerger()
    for key in object_keys:
        try:
            encrypted_file = s3_download_bytes(key)
            decrypted = AESCipher(email).decrypt(encrypted_file)
            pdf_bytes = AttachmentConverter.convert_to_pdf_if_needed(decrypted, key.split("/")[-1])
            merger.append(BytesIO(pdf_bytes))
        except Exception as e:
            logger.error(f"Failed to merge key {key}: {e}")
            continue

    # 4️⃣ Return merged PDF
    output_stream = BytesIO()
    merger.write(output_stream)
    merger.close()
    output_stream.seek(0)

    return StreamingResponse(
        output_stream,
        media_type="application/pdf",
        # headers={
        #     "Content-Disposition": f'inline; filename="merged_{form_id}_{party_email}.pdf"'
        # }
    )


@router.get("/forms/{form_id}/attachments/{filename}", dependencies=[Depends(dynamic_permission_check)])
async def get_attachment(
    form_id: str,
    filename: str,
    party_email: str,
    email: str = Depends(get_email_from_token),
):
    # 1️⃣ Get form path from metadata
    form_data = FormService.get_form(form_id, email)
    form_path = form_data.get("formPath")
    if not form_path:
        raise HTTPException(status_code=404, detail="Form path not found")

    # 2️⃣ Construct S3 key
    s3_key = f"{email}/files/{form_path}/{party_email}/{filename}"

    try:
        response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=s3_key)
        file_bytes = response['Body'].read()

        # 🔐 Decrypt if AES was used
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        decrypted_bytes = cipher.decrypt(file_bytes)

        return StreamingResponse(
            BytesIO(decrypted_bytes),
            media_type=response.get("ContentType", "application/octet-stream"),
            # headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="File not found")
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

