import json
import threading
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import HTTPException

from app.schemas.tracking_schemas import ClientInfo, LogActionRequest
from app.services.metadata_service import MetadataService
from app.services.notification_service import NotificationService
from repositories.s3_repo import (
    load_document_metadata,
    generate_summary_from_trackings,
    save_tracking_metadata,
    store_status,
    load_tracking_metadata,
    update_tracking_status_counts_in_place,
    get_all_document_statuses_flat, get_file_name,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class DocumentTrackingManager:

    @staticmethod
    def get_party_doc_sts(document_id, metadata, party, party_id, tracking_id):
        party_fields = [f for f in metadata.get("fields", []) if f.get("partyId") == party_id]
        logger.info(metadata)
        return {
            "tracking_id": tracking_id,
            "document_id": document_id,
            "validity_date": metadata.get("validityDate"),
            "tracking_status": metadata.get("tracking_status", {"status": "unknown"}),
            "party_id": party_id,
            "party_info": party,
            "fields": party_fields
        }

    @staticmethod
    def get_doc_status(email: str, tracking_id: str, document_id: str) -> dict:
        metadata = MetadataService.get_metadata(email, tracking_id=tracking_id, document_id=document_id)
        if not metadata:
            return {"error": "Document not found"}

        parties = metadata.get("parties", [])
        for index, party in enumerate(parties):
            party["last_party"] = (index == len(parties) - 1)

        tracking_status = metadata.get("tracking_status", {"status": "unknown"})
        validityDate = metadata.get("validityDate")
        response = {
            "tracking_id": tracking_id,
            "document_id": document_id,
            "validity_date":validityDate,
            "tracking_status": tracking_status,
            "parties": parties
        }

        if tracking_status.get("status") == "cancelled":
            response["cancelled_by"] = tracking_status.get("cancelled_by") or metadata.get("cancelled_by")

        return response

    @staticmethod
    def get_all_doc_sts(email: str):
        return get_all_document_statuses_flat(email)

    @staticmethod
    async def log_action(email: str, document_id: str, tracking_id: str, action: str, data: Optional[ClientInfo] = None,
                   party_id: Optional[str] = None, reason: Optional[str] = None, name: Optional[str] = None, user_email: Optional[str] = None):
        try:
            tracking = load_tracking_metadata(email, document_id, tracking_id)
            document_summary = load_document_metadata(email, document_id)
        except Exception as e:
            logger.error(f"[log_action] Failed to load metadata: {e}")
            raise HTTPException(status_code=404, detail="Tracking or document metadata not found")

        current_time = datetime.now(timezone.utc).isoformat()
        context_data = {
            "ip": data.ip if data else None,
            "browser": data.browser if data else None,
            "os": data.os if data else None,
            "device": data.device if data else None,
            "location": {
                "city": data.city if data else None,
                "region": data.region if data else None,
                "country": data.country if data else None,
                "timestamp": data.timestamp if data else None,
                "timezone": data.timezone if data else None
            }
        }

        # Initialize tracking status if not completed
        if tracking.get("tracking_status", {}).get("status") != "completed":
            tracking["tracking_status"] = {
                "status": "in_progress",
                "dateTime": current_time,
                **context_data
            }

        if action == "CANCELLED":
            logger.info(f"[log_action] Marking tracking as CANCELLED: {tracking_id}")
            tracking["tracking_status"].update({
                "status": "cancelled",
                "reason": reason or "No reason provided",
                "dateTime": current_time,
                **context_data
            })

            for party in tracking.get("parties", []):
                party.setdefault("status", {})
                party["status"].setdefault("cancelled", [])
                party["status"]["cancelled"].append({
                    "isCancelled": True,
                    "reason": reason or "No reason provided",
                    "dateTime": current_time,
                    **context_data
                })

            tracking.setdefault("cancelled_by", [])
            tracking["cancelled_by"].append({
                "email": user_email,
                "name": name,
                "reason": reason or "No reason provided",
                "dateTime": current_time,
                **context_data
            })

            try:
                NotificationService.store_notification(
                    email=email,
                    user_email=user_email,
                    document_id=document_id,
                    tracking_id=tracking_id,
                    document_name=await get_file_name(email, document_id),
                    parties_status=tracking.get("parties", []),
                    timestamp=current_time,
                    action="cancelled",
                    party_name=name or "Unknown",
                    party_email=email
                )
            except Exception as e:
                logger.error(f"Failed to store cancel notification: {e}")


        elif action == "DECLINED":
            if not party_id:
                raise HTTPException(status_code=400, detail="Party ID required for DECLINED action")

            logger.info(f"[log_action] Party {party_id} DECLINED with reason: {reason}")

            tracking["tracking_status"] = {
                "status": "declined",
                "reason": reason or "No reason provided",
                "dateTime": current_time,
                **context_data
            }

            party_entry = next((p for p in tracking.get("parties", []) if str(p.get("id")) == str(party_id)), None)
            if not party_entry:
                logger.error(f"[log_action] Party ID {party_id} not found in tracking")
                raise HTTPException(status_code=404, detail="Party ID not found")

            party_entry.setdefault("status", {})
            party_entry["status"]["declined"] = {
                "isDeclined": True,
                "reason": reason or "No reason provided",
                "dateTime": current_time,
                **context_data
            }

            # Store decline notification
            NotificationService.store_notification(
                email=email,
                document_id=document_id,
                tracking_id=tracking_id,
                document_name=await get_file_name(email, document_id),
                parties_status=tracking.get("parties", []),
                timestamp=current_time,
                action="declined",
                party_name=party_entry.get("name", "Unknown"),
                party_email=party_entry.get("email", "Unknown"),
                reason=reason
            )

        else:
            if not party_id:
                raise HTTPException(status_code=400, detail="Party ID required for this action")

            party_entry = next((p for p in tracking.get("parties", []) if str(p.get("id")) == str(party_id)), None)
            if not party_entry:
                logger.error(f"[log_action] Party ID {party_id} not found in tracking")
                raise HTTPException(status_code=404, detail="Party ID not found")

            party_entry.setdefault("status", {})
            status_map = {
                "INITIATED": "sent",
                "RE-INITIATED": "resent",
                "OTP_VERIFIED": "opened",
                "fields_submitted": "resent",
                "REMAINDER": "remainder",
                "ALL_FIELDS_SIGNED": "signed"
            }

            if action in status_map:
                field = status_map[action]

                # If this field does not exist yet, make it a list
                if not isinstance(party_entry["status"].get(field), list):
                    party_entry["status"][field] = []

                # Now append the new record
                party_entry["status"][field].append({
                    f"is{field.capitalize()}": True,
                    "dateTime": current_time,
                    **context_data
                })

                # Special handling for signature completion
                if action == "ALL_FIELDS_SIGNED":
                    # Activate next party
                    party_ids = [str(p["id"]) for p in tracking.get("parties", [])]
                    current_index = party_ids.index(str(party_id))
                    if current_index + 1 < len(tracking["parties"]):
                        next_party = tracking["parties"][current_index + 1]
                        next_party.setdefault("status", {})
                        next_party["status"]["sent"] = {
                            "isSent": True,
                            "dateTime": current_time,
                            **context_data
                        }
                        logger.info(f"[log_action] Next party ID {next_party['id']} marked as SENT")

                    # Check if all  signed
                    all_signed = all(
                        isinstance(party.get("status", {}).get("signed"), list)
                        and party["status"]["signed"]
                        and party["status"]["signed"][-1].get("isSigned") is True
                        for party in tracking["parties"]
                    )

                    if all_signed:
                        tracking["tracking_status"] = {
                            "status": "completed",
                            "dateTime": current_time,
                            **context_data
                        }
                        logger.info(f"[log_action] All parties signed. Tracking marked COMPLETED.")
                else:
                    logger.info(f"[log_action] Updated party {party_id} status: {field}")

        # Save updated tracking metadata
        save_tracking_metadata(email, document_id, tracking_id, tracking)

        # Update document summary
        document_summary["trackings"][tracking_id] = {
            "status": tracking["tracking_status"]["status"],
            "updated_at": current_time
        }
        document_summary["summary"] = generate_summary_from_trackings(document_summary["trackings"])
        store_status(document_id, document_summary, email)

        # Async count update
        threading.Thread(target=update_tracking_status_counts_in_place, args=(email,)).start()

        logger.info(f"[log_action] Final tracking status: {tracking['tracking_status']['status']}")
        logger.debug(f"[log_action] Final parties state: {json.dumps(tracking['parties'], indent=2)}")

    @staticmethod
    def validate_party_and_initialize_status(data, metadata, signed_any):
        if not signed_any:
            raise HTTPException(status_code=404, detail="No matching fields signed for this party")

        party_fields = [f for f in metadata["fields"] if f["partyId"] == data.party_id]
        if not party_fields:
            raise HTTPException(status_code=400, detail="No fields assigned to this party")

        party_status = next((p for p in metadata["parties"] if p["id"] == data.party_id), None)
        if not party_status:
            raise HTTPException(status_code=404, detail="Party ID not found")

        if "status" not in party_status:
            party_status["status"] = {}

        return party_fields, party_status

    @staticmethod
    def initialize_parties_status(doc_data):
        try:
            current_time = datetime.now(timezone.utc).isoformat()
            parties_status = [
                {
                    "id": p.id,
                    "name": p.name,
                    "email": p.email,
                    "color": p.color,
                    "status": {}
                }
                for p in doc_data.parties
            ]
            logger.info(f"Initialized status for {len(parties_status)} parties in document_id: {doc_data.document_id}")
            return parties_status
        except Exception as e:
            logger.exception(f"Error initializing parties status for document_id: {getattr(doc_data, 'document_id', 'unknown')}, error: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to initialize parties status.")

    @staticmethod
    async def log_action_cancel(data: LogActionRequest, client: ClientInfo, email, user_email):
        holder = data.holder
        await document_tracking_manager.log_action(
            email=email,
            document_id=data.document_id,
            tracking_id=data.tracking_id,
            data=client,
            action=data.action,
            party_id=data.party_id,
            reason=data.reason,
            name=holder.name if holder else None,
            user_email=holder.email if holder else None
        )
        return {"message": f"Action '{data.action}' logged successfully."}


document_tracking_manager = DocumentTrackingManager()
