import json

from botocore.exceptions import ClientError

from app.model.form_model import FormModel
from config import config
from database.db_config import s3_client
from utils.logger import logger


class FormRepository:
    @staticmethod
    def create_form(form_id: str, form_data: dict, email: str):
        return FormModel.save_form(form_id, form_data, email)

    @staticmethod
    def get_all_forms(email: str):
        return FormModel.list_forms(email)

    @staticmethod
    def read_form(form_id: str, email: str):
        return FormModel.get_form(form_id, email)

    @staticmethod
    def update_form(form_id: str, updated_data: dict, email: str):
        return FormModel.update_form(form_id, updated_data, email)

    @staticmethod
    def delete_form(form_id: str, email: str):
        return FormModel.delete_form(form_id, email)

    @staticmethod
    def update_trackings(email: str, form_id: str, party_email: str, new_entry: dict):
        return FormModel.send_form(email, form_id, party_email, new_entry)

    @staticmethod
    def get_tracking(email: str, form_id: str, party_email: str):
        return FormModel.get_form_track(email, form_id, party_email)

    @staticmethod
    def validate_form(form, values):
        FormModel.validate_form_values(form, values)

    @staticmethod
    async def upload_pdf(email: str, form_id: str, party_email: str, pdf_bytes: bytes, form_path: str, formTitle: str):
        return await FormModel.upload_pdfs(email=email, form_id=form_id, party_email=party_email, pdf_bytes=pdf_bytes, form_path=form_path, formTitle=formTitle)

    @staticmethod
    async def get_pdf(email: str, form_id: str, party_email: str, form: dict):
        return await FormModel.get_pdfs(email, form_id, party_email, form)

    @staticmethod
    def update_tracking_status(email: str, form_id: str, party_email: str, new_status: str,request ):
        return FormModel.update_tracking_status_by_party(email, form_id, party_email, new_status,request )

    @staticmethod
    def get_user_data(email: str, form_id: str) -> dict:
        """
        Retrieve form_user_data.json from S3 for a specific form and email.
        """
        key = f"{email}/forms/submissions/{form_id}/form_user_data.json"
        try:
            resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"No form submission data found at {key}")
                return None
            raise

    @staticmethod
    async def get_tracking_data(email: str, form_id: str) -> dict:
        """
        Retrieve trackings.json for a form from S3.
        """
        key = f"{email}/forms/submissions/{form_id}/trackings.json"
        try:
            resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"Submission tracking data not found at {key}")
                return None
            raise

    @staticmethod
    def list_form_folders(email: str) -> list[str]:
        """
        List all form submission folders for a user.
        """
        prefix = f"{email}/forms/submissions/"
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=config.S3_BUCKET, Prefix=prefix, Delimiter="/")

        form_folders = []
        for page in pages:
            for cp in page.get("CommonPrefixes", []):
                form_folders.append(cp.get("Prefix"))
        return form_folders



    @staticmethod
    def get_trackings(email: str, form_id: str) -> dict | None:
        """
        Get trackings.json for a given form.
        """
        key = f"{email}/forms/submissions/{form_id}/trackings.json"
        try:
            obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise
        except Exception as e:
            logger.warning(f"⚠️ Error reading {key}: {e}")
            return None
    @staticmethod
    async def list_form_ids( email: str) -> list[str]:
        prefix = f"{email}/forms/submissions/"
        paginator = s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(
            Bucket=config.S3_BUCKET, Prefix=prefix, Delimiter="/"
        )

        form_ids = []
        for page in page_iterator:
            for cp in page.get("CommonPrefixes", []):
                form_folder = cp.get("Prefix")
                form_id = form_folder.rstrip("/").split("/")[-1]
                form_ids.append(form_id)
        return form_ids







