import uuid
from typing import Optional
from repositories.s3_repo import s3_upload_json

from central_logger import CentralLogger
logger = CentralLogger.get_logger()

class NotificationService:
    @staticmethod
    def store_notification(
        email: str,
        user_email: str,
        document_id: str,
        tracking_id: str,
        document_name: str,
        parties_status: list,
        timestamp: str,
        action: Optional[str] = "completed",
        party_name: Optional[str] = None,
        party_email: Optional[str] = None,
        reason: Optional[str] = None
    ):
        try:
            # Default values based on action
            if action == "cancelled":
                status = "cancelled"
                message = f"Document '{document_name}' was cancelled by {party_name or 'Unknown'}."
            elif action == "declined":
                status = "declined"
                reason_text = f" Reason: {reason}" if reason else ""
                message = f"Document '{document_name}' was declined by {party_name or 'Unknown'}." + reason_text
            elif action == "dispatched":
                status = "dispatched"
                reason_text = f" Reason: {reason}" if reason else ""
                message = f"Document '{document_name}' was dispatched to {party_name or 'Unknown'}." + reason_text
            elif action == "failed":
                status = "failed"
                reason_text = f" Reason: {reason}" if reason else ""
                message = f"Document '{document_name}' failed to dispatch to {party_name or 'Unknown'}." + reason_text
            else:
                status = "completed"
                message = f"All parties have signed the document '{document_name}'. (Tracking ID: {tracking_id})"
            notification_id = f"notif-{uuid.uuid4().hex[:8]}"
            notification = {
                "notification_id": notification_id,
                "document_id": document_id,
                "tracking_id": tracking_id,
                "party_name": party_name or (parties_status[0].get("name", "-") if parties_status else "-"),
                "party_email": party_email or (parties_status[0].get("email", "-") if parties_status else "-"),
                "status": status,
                "message": message,
                "timestamp": timestamp,
                "read": False,
                "parties": [
                    {
                        "id": str(p.get("id")),
                        "name": p.get("name"),
                        "email": p.get("email"),
                        "status": p.get("status", status)
                    } for p in parties_status
                ]
            }

            s3_key = f"{email}/notifications/{user_email}/{notification_id}.json"
            s3_upload_json(notification, s3_key)
            logger.info(f"[NotificationService] Notification stored: {s3_key}")
        except Exception as e:
            logger.exception(f"[NotificationService] Failed to store notification: {e}")

    @staticmethod
    async def store_form_notification(
            email: str,
            user_email: str,
            form_id: str,
            form_title: str,
            party_email: str,
            timestamp: str,
            party_name: str = None
    ):
        try:
            notification_id = f"notif-{uuid.uuid4().hex[:8]}"
            message = f"Form '{form_title}' has been successfully submitted by {party_name or party_email}."

            notification = {
                "notification_id": notification_id,
                "form_id": form_id,
                "party_name": party_name,
                "party_email": party_email,
                "status": "completed",
                "message": message,
                "timestamp": timestamp,
                "read": False,
                "parties": [
                    {
                        "party_name": party_name,
                        "party_email": party_email,
                        "status": "completed",
                    }
                ]
            }

            s3_key = f"{email}/notifications/{notification_id}.json"
            s3_upload_json(notification, s3_key)
            logger.info(f"[FormNotification] Notification stored: {s3_key}")

        except Exception as e:
            logger.exception(f"[FormNotification] Failed to store notification: {e}")

notification_service = NotificationService()