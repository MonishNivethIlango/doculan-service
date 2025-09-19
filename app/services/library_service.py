import uuid
import logging
from io import BytesIO
from pathlib import PurePosixPath
from starlette.responses import JSONResponse, StreamingResponse
from datetime import datetime, timezone
from fastapi import HTTPException
from typing import Dict, Any, Optional, List
from app.schemas.template_schema import TemplateLibrariesCreate, TemplateLibrariesUpdate
from app.services.security_service import EncryptionService, AESCipher
from repositories.s3_repo import s3_client
from botocore.exceptions import ClientError
import json
from config import config
from repositories.s3_repo import s3_head_upload, get_json, put_json

logger = logging.getLogger("doculan.library_service")


class LibraryService:
    def __init__(self, storage):
        self.storage = storage


    def generate_library_id(self) -> str:
        return str(uuid.uuid4())

    def _get_library_key(self, email: str, library_id: str, filename: str, path_prefix: str = "") -> str:
        """
        Construct the S3 key (or storage path) for a file inside a library.
        Example: user@example.com/libraries/{library_id}/path/filename.pdf
        """
        return str(PurePosixPath(email, "libraries", library_id, path_prefix, filename))

    async def library_upload(self, email: str, files, path: str = None, overwrite: bool = False):
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        raw_path = (path or "").strip().strip("/")
        existing_files = []
        library_id = self.generate_library_id()

        # ✅ Phase 1: Check if files already exist
        for file in files:
            full_path = f"{raw_path}/{file.filename}" if raw_path else file.filename
            lib_key = self._get_library_key(email, library_id, file.filename, raw_path)

            try:
                await s3_head_upload(lib_key)
                if not overwrite:
                    existing_files.append(full_path)
            except ClientError as e:
                if e.response['Error']['Code'] != "404":
                    logger.error(f"S3 check error for {file.filename}: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Error checking '{file.filename}' in S3")

        if existing_files:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Upload rejected. One or more files already exist in the library.",
                    "existing_files": existing_files
                }
            )

        # ✅ Phase 2: Upload files to library
        results = []
        for file in files:
            full_path = f"{raw_path}/{file.filename}" if raw_path else file.filename
            try:
                result = self.storage.upload_library(email, library_id, file, raw_path, overwrite, cipher)
                results.append({
                    "library_id": library_id,
                    "filename": full_path,
                    "status": "uploaded"
                })
            except Exception as e:
                logger.error(f"Upload failed for {file.filename}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload {file.filename}: {str(e)}"
                )

        return results

    async def get_document(self, result, return_pdf: bool):
        try:
            if return_pdf:
                if isinstance(result, dict) and "error" in result:
                    return JSONResponse(content=result, status_code=400)
                return StreamingResponse(BytesIO(result), media_type="application/pdf")
            return JSONResponse(content=result)
        except Exception as e:
            logger.error("Failed to return PDF/JSON response: %s", e)
            return JSONResponse(content={"error": str(e)}, status_code=500)




class TemplateLibraryManager:
    def __init__(self, email: str, user_email: str):
        self.email = email
        self.user_email = user_email

    def _get_template_key(self, template_name: str) -> str:
        """All templates go under a single library path (no global/local distinction)."""
        return f"libraries/E-sign/templates/{template_name}.json"

    def _get_prefix(self) -> str:
        return f"libraries/E-sign/templates/"

    def save_template(self, template_name: str, template_data: dict):
        key = self._get_template_key(template_name)
        try:
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=key,
                Body=json.dumps(template_data, indent=2),
                ContentType="application/json",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )
            logger.info(f"Saved template: {key}")
        except Exception as e:
            logger.exception(f"Failed to save template: {e}")
            raise HTTPException(status_code=500, detail="Failed to save template")

    def load_template_by_name(self, template_name: str) -> Optional[dict]:
        key = self._get_template_key(template_name)
        try:
            raw = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)["Body"].read().decode("utf-8")
            return json.loads(raw)
        except ClientError:
            logger.warning(f"Template not found: {key}")
            return None

    def load_all_templates(self) -> Dict[str, Any]:
        prefix = self._get_prefix()
        templates = {}
        try:
            response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if not key.endswith(".json"):
                    continue
                try:
                    raw = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)["Body"].read().decode("utf-8")
                    name = key.split("/")[-1].replace(".json", "")
                    templates[name] = json.loads(raw)
                except Exception as e:
                    logger.warning(f"Failed to load template from {key}: {e}")
        except ClientError as e:
            logger.error(f"Failed to list templates: {e}")
        return templates

    def create_template(self, data: TemplateLibrariesCreate, template_name: str, fields, parties):
        existing = self.load_template_by_name(template_name)
        if existing:
            raise HTTPException(status_code=400, detail="Template already exists")

        template_data = {
            "fields": [f.dict() for f in fields],
            "parties": [p.dict() for p in parties],
            "library_id": data.library_id
        }

        self.save_template(template_name, template_data)
        return {"message": f"Template '{template_name}' created."}

    def get_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        return self.load_template_by_name(template_name)

    def get_all_templates(self):
        return self.load_all_templates()

    def delete_template(self, template_name: str):
        key = self._get_template_key(template_name)
        try:
            s3_client.delete_object(Bucket=config.S3_BUCKET, Key=key)
            logger.info(f"Deleted template: {key}")
            return {"message": f"Template '{template_name}' deleted."}
        except ClientError:
            raise HTTPException(status_code=404, detail="Template not found")

    def update_template(self, data: TemplateLibrariesUpdate, template_name: str, fields=None, parties=None):
        template = self.load_template_by_name(template_name)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if fields is not None:
            template["fields"] = [f.dict() for f in fields]
        if parties is not None:
            template["parties"] = [p.dict() for p in parties]
        if data.library_id is not None:
            template["library_id"] = data.library_id

        self.save_template(template_name, template)
        return {"message": f"Template '{template_name}' updated."}







class LibraryFormService:
    """
    Service for managing library forms and their associated tags in S3.
    """

    # ----------------------------
    # Internal helpers
    # ----------------------------
    @staticmethod
    def _get_library_form_key(library_form_id: str) -> str:
        """
        Build the S3 key for storing a form in the library.
        """
        return f"libraries/forms/{library_form_id}.json"

    # ----------------------------
    # Tags Management
    # ----------------------------
    @staticmethod
    def update_tags(library_form_id: str, form_title: str, tags: List[str]):
        """
        Update tags.json in S3 to associate tags with a form.
        Structure:
        {
            "tag1": [{"formId": "abc", "formTitle": "Form A"}],
            "tag2": [{"formId": "xyz", "formTitle": "Form B"}]
        }
        """
        key = "libraries/metadata/library/tags.json"
        tags_json: Dict = get_json(key) or {}

        for tag in tags:
            if tag not in tags_json:
                tags_json[tag] = []

            # Prevent duplicate entries
            if not any(f["library_form_id"] == library_form_id for f in tags_json[tag]):
                tags_json[tag].append({"library_form_id": library_form_id, "formTitle": form_title})

        put_json(key, tags_json)

    # ----------------------------
    # CRUD Methods
    # ----------------------------
    @classmethod
    def get_form(cls, library_form_id: str) -> dict:
        """
        Retrieve a form by its library_form_id.
        """
        key = cls._get_library_form_key(library_form_id)
        try:
            response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
            return json.loads(response["Body"].read().decode("utf-8"))
        except s3_client.exceptions.NoSuchKey:
            return {}
        except Exception as e:
            logger.error(f"Error fetching library form {library_form_id}: {e}")
            raise HTTPException(status_code=500, detail="Unable to fetch form")

    @classmethod
    def save_form(cls, library_form_id: str, data: dict):
        """
        Save or update a form in the library.
        """
        key = cls._get_library_form_key(library_form_id)
        try:
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=key,
                Body=json.dumps(data, indent=2),
                ContentType="application/json",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID,
            )

            # Update tags metadata if tags exist
            if "tags" in data and isinstance(data["tags"], list):
                cls.update_tags(library_form_id, data.get("formTitle", ""), data["tags"])

        except Exception as e:
            logger.error(f"Error saving library form {library_form_id}: {e}")
            raise HTTPException(status_code=500, detail="Unable to save form")

    @classmethod
    def delete_form(cls, library_form_id: str):
        """
        Delete a form from the library.
        """
        key = cls._get_library_form_key(library_form_id)
        try:
            s3_client.delete_object(Bucket=config.S3_BUCKET, Key=key)
            logger.info(f"Deleted library form {library_form_id}")
        except ClientError as e:
            logger.error(f"Failed to delete library form {library_form_id}: {e}")
            raise HTTPException(status_code=404, detail="Form not found")

    @classmethod
    def list_forms(cls):
        """
        List all forms stored in the library.
        """
        prefix = "libraries/forms/"
        try:
            response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
            form_items = []

            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".json"):
                    library_form_id = key.split("/")[-1].replace(".json", "")
                    form_data = cls.get_form(library_form_id)
                    form_items.append({"libraryFormId": library_form_id, **form_data})

            return form_items

        except Exception as e:
            logger.error(f"Failed to list library forms: {e}")
            raise HTTPException(status_code=500, detail="Unable to list forms")

    @classmethod
    def update_form(cls, library_form_id: str, form_data: dict):
        """
        Update an existing form in the library.
        """
        existing_form = cls.get_form(library_form_id)
        if not existing_form:
            raise HTTPException(status_code=404, detail="Form not found")

        # Merge updates
        existing_form.update(form_data)
        existing_form["updated_at"] = datetime.now(timezone.utc).isoformat()

        cls.save_form(library_form_id, existing_form)
        return {"message": f"Library form {library_form_id} updated successfully"}

