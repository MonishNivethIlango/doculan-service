from fastapi import HTTPException
from typing import Dict, Any, Optional

from app.schemas.template_schema import TemplateCreate, TemplateUpdate
from utils.logger import logger
from repositories.s3_repo import s3_client
from botocore.exceptions import ClientError
import json
from config import config

class TemplateManager:
    def __init__(self, email: str, user_email: str):
        self.email = email
        self.user_email = user_email


    def _get_template_key(self, template_name: str, is_global: bool) -> str:
        return f"{self.email}/Global/E-Sign-template/{template_name}.json" if is_global else f"{self.email}/templates/{self.user_email}/templates/{template_name}.json"

    def _get_prefix(self, is_global: bool) -> str:
        return f"{self.email}/Global/E-Sign-template/" if is_global else f"{self.email}/templates/{self.user_email}/templates/"

    def save_template(self, template_name: str, template_data: dict, is_global: bool):
        key = self._get_template_key(template_name, is_global)
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

    def load_template_by_name(self, template_name: str, is_global: bool) -> Optional[dict]:
        key = self._get_template_key(template_name, is_global)
        try:
            raw = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)["Body"].read().decode("utf-8")
            return json.loads(raw)
        except ClientError:
            logger.warning(f"Template not found: {key}")
            return None

    def load_all_templates(self, is_global: bool) -> Dict[str, Any]:
        prefix = self._get_prefix(is_global)
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

    def create_template(self, data: TemplateCreate, template_name: str, fields, parties, is_global=False):
        existing = self.load_template_by_name(template_name, is_global)
        if existing:
            raise HTTPException(status_code=400, detail="Template already exists")

        template_data = {
            "fields": [f.dict() for f in fields],
            "parties": [p.dict() for p in parties],
            "document_id":data.document_id
        }

        self.save_template(template_name, template_data, is_global)
        return {"message": f"Template '{template_name}' created."}

    def get_template(self, template_name: str, is_global: bool = False) -> Optional[Dict[str, Any]]:
        return self.load_template_by_name(template_name, is_global)

    def get_all_templates(self):
        local_templates = self.load_all_templates(is_global=False)
        global_templates = self.load_all_templates(is_global=True)
        return {
            "local": local_templates,
            "global": global_templates
        }

    def delete_template(self, template_name: str, is_global: bool = False):
        key = self._get_template_key(template_name, is_global)
        try:
            s3_client.delete_object(Bucket=config.S3_BUCKET, Key=key)
            logger.info(f"Deleted template: {key}")
            return {"message": f"Template '{template_name}' deleted."}
        except ClientError:
            raise HTTPException(status_code=404, detail="Template not found")

    def update_template(self, data: TemplateUpdate, template_name: str, fields=None, parties=None, is_global=False):
        template = self.load_template_by_name(template_name, is_global)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if fields is not None:
            template["fields"] = [f.dict() for f in fields]
        if parties is not None:
            template["parties"] = [p.dict() for p in parties]
        if data.document_id is not None:
            template["document_id"] = data.document_id

        self.save_template(template_name, template, is_global)
        return {"message": f"Template '{template_name}' updated."}