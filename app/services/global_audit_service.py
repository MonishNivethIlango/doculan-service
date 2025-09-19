from datetime import datetime, timezone
from typing import Dict, Optional, List
from fastapi import HTTPException, APIRouter
from database.db_config import s3_client
from repositories.s3_repo import append_logs, get_logs

router = APIRouter()


class GlobalAuditService:
    @staticmethod
    def _get_doc_audit_key(email: str) -> str:
        return f"{email}/audit/all_logs_document.json"

    @staticmethod
    def _get_form_audit_key(email: str) -> str:
        return f"{email}/audit/all_logs_form.json"

    @staticmethod
    def _append_log(key: str, entry: dict):
        try:
            append_logs(entry, key)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to write audit log: {str(e)}")



    @staticmethod
    def _create_entry(
        entity: str,
        entity_id: str,
        action: str,
        actor: Dict,
        metadata: Optional[Dict] = None,
        targets: Optional[List[Dict]] = None
    ) -> Dict:
        return {
            "entity": entity,
            "entity_id": entity_id,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "targets": targets or [],
            "metadata": metadata or {}
        }

    @staticmethod
    def log_document_action(
        email: str,
        document_id: str,
        action: str,
        actor: Dict,
        metadata: Optional[Dict] = None,
        targets: Optional[List[Dict]] = None
    ):
        key = GlobalAuditService._get_doc_audit_key(email)
        entry = GlobalAuditService._create_entry("document", document_id, action, actor, metadata, targets)
        GlobalAuditService._append_log(key, entry)

    @staticmethod
    def log_form_action(
        email: str,
        form_id: str,
        action: str,
        actor: Dict,
        metadata: Optional[Dict] = None,
        targets: Optional[List[Dict]] = None
    ):
        key = GlobalAuditService._get_form_audit_key(email)
        entry = GlobalAuditService._create_entry("form", form_id, action, actor, metadata, targets)
        GlobalAuditService._append_log(key, entry)

    @staticmethod
    def get_document_logs(email: str) -> List[Dict]:
        key = GlobalAuditService._get_doc_audit_key(email)
        try:
            return get_logs(key)
        except s3_client.exceptions.NoSuchKey:
            return []
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch document audit logs: {str(e)}")



    @staticmethod
    def get_form_logs(email: str) -> List[Dict]:
        key = GlobalAuditService._get_form_audit_key(email)
        try:
            return get_logs(key)
        except s3_client.exceptions.NoSuchKey:
            return []
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch form audit logs: {str(e)}")

    @staticmethod
    def get_document_logs_by_id(email: str, document_id: str) -> List[Dict]:
        logs = GlobalAuditService.get_document_logs(email)
        return [log for log in logs if log.get("entity_id") == document_id]

    @staticmethod
    def get_form_logs_by_id(email: str, form_id: str) -> List[Dict]:
        logs = GlobalAuditService.get_form_logs(email)
        return [log for log in logs if log.get("entity_id") == form_id]



