import base64
import logging
import tempfile
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from fastapi import HTTPException
from starlette.responses import FileResponse
from app.schemas.tracking_schemas import DocumentRequest, SignField
from config import config
from database.db_config import s3_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MetadataService:

    @staticmethod
    def load_metadata_from_s3(email: str, tracking_id: str, document_id: str):
        try:
            from repositories.s3_repo import load_meta_s3
            return load_meta_s3(email, tracking_id=tracking_id, document_id=document_id)
        except s3_client.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail="Document metadata not found.")

    @staticmethod
    def save_metadata_to_s3(email: str, document_id: str, tracking_id: str, metadata: dict):
        from repositories.s3_repo import save_meta_s3
        save_meta_s3(email, document_id, tracking_id, metadata)

    @staticmethod
    def upload_metadata(email: str, doc_data: DocumentRequest, tracking_metadata: dict, store_as_default: bool = False):
        try:
            from repositories.s3_repo import upload_meta_s3
            upload_meta_s3(email, doc_data, tracking_metadata, store_as_default)
            logger.info(f"Metadata uploaded successfully for document_id: {doc_data.document_id}, email: {email}")
        except Exception as e:
            logger.exception(f"Failed to upload metadata: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to upload metadata to S3.")

    @staticmethod
    def upload_sign_metadata(email: str, doc_data: SignField, tracking_metadata: dict):
        from repositories.s3_repo import upload_sign_meta_s3
        document_id = doc_data.document_id
        tracking_id = doc_data.tracking_id
        upload_sign_meta_s3(email, document_id, tracking_id, tracking_metadata)

    @staticmethod
    def get_metadata(email: str, tracking_id: str, document_id):
        try:
            from repositories.s3_repo import get_meta_s3
            return get_meta_s3(email, tracking_id=tracking_id, document_id=document_id)
        except s3_client.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail="Tracking ID not found")


    @staticmethod
    def get_metadata_signed_party(email: str, tracking_id: str, document_id: str):
        metadata = MetadataService.get_metadata(email, tracking_id, document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Tracking ID not found")
        return metadata

    @staticmethod
    def get_party_meta(email: str, document_id: str, party_id: str, tracking_id: str):
        metadata = MetadataService.get_metadata(email, tracking_id, document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Tracking metadata not found")
        party = next((p for p in metadata.get("parties", []) if p.get("id") == party_id), None)
        if not party:
            raise HTTPException(status_code=404, detail="Party ID not found")
        return metadata, party

    @staticmethod
    def get_email_by_party_id(email: str, tracking_id: str, document_id: str, party_id: str):
        try:
            metadata = MetadataService.get_metadata(email, tracking_id, document_id)
            if not metadata:
                raise HTTPException(status_code=404, detail="Tracking metadata not found")

            party = next((p for p in metadata.get("parties", []) if p.get("id") == party_id), None)
            if not party:
                raise HTTPException(status_code=404, detail=f"Party ID '{party_id}' not found")

            party_email = party.get("email")
            if not party_email:
                raise HTTPException(status_code=404, detail=f"Email not found for party ID '{party_id}'")

            return {"email": party_email}

        except HTTPException as http_exc:
            logger.error(f"[Email Lookup] HTTPException: {http_exc.detail}")
            raise http_exc

        except Exception as e:
            logger.exception("[Email Lookup] Unexpected error occurred while retrieving email")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve email: {str(e)}")

    @staticmethod
    def get_form_email_by_party_id(form_id: str, party_id: str, form_tracking_id: str, user_email: str):
        try:
            from app.services.FormService import FormService
            form_service = FormService()
            tracking_entries = form_service.get_tracking_entry(form_id, form_tracking_id, user_email)

            if not tracking_entries:
                raise HTTPException(status_code=404, detail="No tracking data found for this form")

            for entry in tracking_entries:
                if form_tracking_id and entry.get("form_tracking_id") != form_tracking_id:
                    continue

                party = next((p for p in entry.get("parties", []) if str(p.get("id")) == str(party_id)), None)
                if party:
                    party_email = party.get("email")
                    if not party_email:
                        raise HTTPException(status_code=404, detail="Email not found for the party")
                    return {"email": party_email}

            raise HTTPException(status_code=404, detail="Party ID not found in tracking entries")
        except Exception as e:
            logger.exception("Failed to get party email")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve party email: {str(e)}")

    @staticmethod
    def update_metadata_fields_with_signed_values(data, metadata: dict, signed_any: bool):
        updated_fields = []

        for field_group in data.fields:
            for field_data in field_group.fields_ids:
                for field in metadata.get("fields", []):
                    if field["id"] == field_data.field_id and field["partyId"] == data.party_id:
                        field["signed"] = True
                        field["value"] = field_data.value
                        if getattr(field_data, "font", None):
                            field["font"] = field_data.font
                        if getattr(field_data, "style", None):
                            field["style"] = field_data.style
                        field["signed_at"] = datetime.now(timezone.utc).isoformat()
                        updated_fields.append(field["id"])
                        signed_any = True
                        break

        if updated_fields:
            print(f"Updated fields: {updated_fields}")
        return signed_any

    @staticmethod
    def generate_document_metadata(email: str, doc_data: DocumentRequest, parties_status: list, tracking_id: str) -> dict:
        try:
            # if not doc_data.document_id:
            #     logger.error(f"Missing document_id for tracking_id: {tracking_id}")
            #     raise HTTPException(status_code=400, detail="Missing document_id.")
            #
            # bucket_name = config.S3_BUCKET  # Replace with actual bucket
            # document_key = f"{email}/metadata/document/{doc_data.document_id}.json"
            #
            # # Verify existence of document metadata in S3
            # try:
            #     s3_client.head_object(Bucket=bucket_name, Key=document_key)
            # except ClientError as e:
            #     if e.response['Error']['Code'] == "404":
            #         logger.warning(f"Document not found in S3: {document_key}")
            #         raise HTTPException(status_code=404, detail="Document metadata not found in S3.")
            #     else:
            #         logger.exception("Unexpected S3 error")
            #         raise HTTPException(status_code=500, detail="Error accessing S3.")

            metadata = {
                "tracking_id": tracking_id,
                "document_id": doc_data.document_id,
                "parties": parties_status,
                "fields": [f.dict() for f in doc_data.fields],
                "email_response": [er.dict() for er in doc_data.email_response],
                "cc_emails": doc_data.cc_emails if doc_data.cc_emails else [],
                "validityDate": doc_data.validityDate,
                "remainder": doc_data.remainder,
                "pdfSize": doc_data.pdfSize.dict() if doc_data.pdfSize else {},
                "holder": doc_data.holder.dict() if doc_data.holder else {},

            }

            logger.info(f"Successfully generated document metadata for tracking_id: {tracking_id}")
            return metadata

        except HTTPException:
            raise  # Propagate FastAPI exceptions
        except Exception as e:
            logger.exception(f"Unexpected failure for tracking_id: {tracking_id}")
            raise HTTPException(status_code=500, detail="Failed to generate document metadata.")
