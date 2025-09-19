import asyncio
import threading

from fastapi import HTTPException
from datetime import datetime, timezone

from app.services.certificate_service import certificate_service
from app.services.email_service import EmailService, email_service
from app.services.metadata_service import MetadataService
from app.services.notification_service import NotificationService
from app.services.pdf_form_field_renderer_service import generate_signature_b64_from_fontname
from app.services.pdf_service import PDFSigner
from app.services.tracking_service import TrackingService
from auth_app.app.database.connection import db
from utils.drive_client import get_base64_logo, count_pages_from_base64_pdf, format_datetime
from utils.logger import logger
import base64
import uuid
from typing import List, Dict, Any
from app.services.global_audit_service import GlobalAuditService
from app.services.audit_service import DocumentTrackingManager, document_tracking_manager
from auth_app.app.utils.security import create_signature_token
from repositories.s3_repo import generate_summary_from_trackings, \
    load_all_json_from_prefix, store_tracking_status, save_tracking_metadata, store_status, \
    update_tracking_status_counts_in_place, load_tracking_metadata, load_document_metadata, get_document_name, \
    upload_file, s3_download_string, s3_delete_object, s3_upload_bytes, get_signature_entry, get_file_name
from app.schemas.form_schema import EmailResponse
from app.schemas.tracking_schemas import DocumentRequest, SignField, ClientInfo, Address, DocumentResendRequest
from utils.scheduler_manager import SchedulerManager
from utils.security import format_user_datetime


def format_holder_address(address: dict) -> str:
    lines = [
        address.get("address_line_1"),
        address.get("address_line_2"),
        address.get("city"),
        address.get("state"),
        address.get("zipcode"),
        address.get("country"),
    ]
    return ', '.join(filter(None, lines))



class SignatureHandler:
    def __init__(self, email: str, user_email: str, doc_data: DocumentRequest, request, store_as_default: bool = False):
        self.email = email
        self.user_email = user_email
        self.doc_data = doc_data
        self.store_as_default = store_as_default
        self.tracking_id = str(uuid.uuid4())

    async def initiate_signature_flow(self):
        try:
            # ✅ Initialize party status
            parties_status = document_tracking_manager.initialize_parties_status(self.doc_data)
            tracking_metadata = MetadataService.generate_document_metadata(
                self.email, self.doc_data, parties_status, self.tracking_id
            )
            MetadataService.upload_metadata(self.email, self.doc_data, tracking_metadata, self.store_as_default)

            # ✅ Scheduled flow
            if (
                self.doc_data.scheduled_datetime
                and self.doc_data.scheduled_datetime > datetime.now(timezone.utc)
            ):
                try:
                    await SchedulerManager.add_job(
                        document_id=self.doc_data.document_id,
                        tracking_id=self.tracking_id,
                        action="send_email",
                        schedule_time=self.doc_data.scheduled_datetime,
                        email=self.email,
                        user_email=self.user_email,
                        data=self.doc_data.dict()
                    )
                    logger.info(
                        "[INIT FLOW] Scheduled document %s with tracking %s at %s",
                        self.doc_data.document_id, self.tracking_id, self.doc_data.scheduled_datetime.isoformat()
                    )
                except Exception as e:
                    logger.error(
                        "[INIT FLOW] Failed to schedule job for document %s, tracking %s: %s",
                        self.doc_data.document_id, self.tracking_id, str(e)
                    )
                    raise HTTPException(status_code=500, detail="Failed to schedule signature initiation.")

                # ✅ Log initial status
                first_party = self.doc_data.parties[0]
                logger.info(f"Party {first_party}")
                await document_tracking_manager.log_action(
                    self.email, self.doc_data.document_id, self.tracking_id,
                    "INITIATED", self.doc_data.client_info, first_party.id
                )
                return {"tracking_id": self.tracking_id, "status": "scheduled"}

            # ✅ Immediate flow
            await self.initiate_signing_process()
            return {"tracking_id": self.tracking_id, "status": "sent"}

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(
                "[INIT FLOW] Failed to initiate flow for document %s, tracking %s: %s",
                getattr(self.doc_data, "document_id", "unknown"), self.tracking_id, str(e)
            )
            raise HTTPException(status_code=500, detail="Failed to initiate signature flow.")

    async def initiate_signing_process(self):
        try:
            first_party = self.doc_data.parties[0]
            logger.debug("[SIGN PROCESS] Starting for party %s in document %s",
                         first_party.id, self.doc_data.document_id)

            token_data = await create_signature_token(
                sent_email=first_party.email,
                tracking_id=self.tracking_id,
                party_id=first_party.id,
                email=self.user_email,
                document_id=self.doc_data.document_id,
                validity_date_str=self.doc_data.validityDate,
                remainder_days=self.doc_data.remainder
            )
            token = token_data["token"]
            validity_datetime = token_data["validity_datetime"]

            # ✅ Send email
            await email_service.send_link(
                reply_name=self.doc_data.holder.name,
                reply_email=self.doc_data.holder.email,
                recipient_email=first_party.email,
                document_id=self.doc_data.document_id,
                tracking_id=self.tracking_id,
                party_id=first_party.id,
                party_name=first_party.name,
                token=token,
                email_response=self.doc_data.email_response,
                validity_datetime=validity_datetime,
                cc_emails=self.doc_data.cc_emails
            )

            logger.info(
                "[SIGN PROCESS] Email sent to %s for document %s, tracking %s",
                first_party.email, self.doc_data.document_id, self.tracking_id
            )

            # ✅ Log initiation
            await document_tracking_manager.log_action(
                self.email, self.doc_data.document_id, self.tracking_id,
                "INITIATED", self.doc_data.client_info, first_party.id
            )

        except ValueError as ve:
            logger.warning(
                "[SIGN PROCESS] Invalid configuration for document %s, tracking %s: %s",
                self.doc_data.document_id, self.tracking_id, str(ve)
            )
            raise HTTPException(status_code=400, detail=str(ve))
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(
                "[SIGN PROCESS] Failed for document %s, tracking %s: %s",
                getattr(self.doc_data, "document_id", "unknown"), self.tracking_id, str(e)
            )
            raise HTTPException(status_code=500, detail="Failed to initiate signing process.")
    @staticmethod
    async def initiate_singing_schedule(doc_data:DocumentRequest, tracking_id, email, user_email):
        try:
            first_party = doc_data.parties[0]
            logger.debug("[SIGN PROCESS] Starting for party %s in document %s",
                         first_party.id, doc_data.document_id)

            token_data = await create_signature_token(
                sent_email=first_party.email,
                tracking_id=tracking_id,
                party_id=first_party.id,
                email=user_email,
                document_id=doc_data.document_id,
                validity_date_str=doc_data.validityDate,
                remainder_days=doc_data.remainder
            )
            token = token_data["token"]
            validity_datetime = token_data["validity_datetime"]

            # ✅ Send email
            await email_service.send_link(
                reply_name=doc_data.holder.name,
                reply_email=doc_data.holder.email,
                recipient_email=first_party.email,
                document_id=doc_data.document_id,
                tracking_id=tracking_id,
                party_id=first_party.id,
                party_name=first_party.name,
                token=token,
                email_response=doc_data.email_response,
                validity_datetime=validity_datetime,
                cc_emails=doc_data.cc_emails
            )

            logger.info(
                "[SIGN PROCESS] Email sent to %s for document %s, tracking %s",
                first_party.email, doc_data.document_id, tracking_id
            )

            # ✅ Log initiation
            await document_tracking_manager.log_action(
                email, doc_data.document_id, tracking_id,
                "INITIATED", doc_data.client_info, first_party.id
            )

        except ValueError as ve:
            logger.warning(
                "[SIGN PROCESS] Invalid configuration for document %s, tracking %s: %s",
                doc_data.document_id, tracking_id, str(ve)
            )
            raise HTTPException(status_code=400, detail=str(ve))
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(
                "[SIGN PROCESS] Failed for document %s, tracking %s: %s",
                getattr(doc_data, "document_id", "unknown"), tracking_id, str(e)
            )
            raise HTTPException(status_code=500, detail="Failed to initiate signing process.")

    @staticmethod
    async def sign_field(email: str, user_email: str, data: SignField):
        try:
            try:
                metadata = MetadataService.get_metadata(email, data.tracking_id, data.document_id)
                if not metadata:
                    raise HTTPException(status_code=404, detail="Tracking ID not found")
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="Tracking ID not found")
            # party_statuses = metadata.get("parties", {})
            # party_info = party_statuses.get(data.party_id)
            #
            # if party_info:
            #     for field, entries in party_info.get("status", {}).items():
            #         # Normalize to list if it's a single dict
            #         if isinstance(entries, dict):
            #             entries = [entries]
            #
            #         if isinstance(entries, list):
            #             already_signed = any(entry.get(f"is{field.capitalize()}") for entry in entries)
            #             if already_signed:
            #                 raise HTTPException(
            #                     status_code=400,
            #                     detail=f"This party has already signed the field '{field}'"
            #                 )

            signed_any = MetadataService.update_metadata_fields_with_signed_values(data, metadata, signed_any=False)

            party_fields, party_status = document_tracking_manager.validate_party_and_initialize_status(
                data, metadata, signed_any
            )

            pdfSigner = PDFSigner()
            await pdfSigner.finalize_party_signing_and_render_pdf(data, data.client_info, email, metadata, party_fields, party_status)


            signed_pdf_base64 , file_name= await pdfSigner.render_signed_pdf(
                email=email,
                fields=metadata["fields"],
                document_id=data.document_id,
                tracking_id=data.tracking_id,
                pdf_size=metadata.get("pdfSize", {"pdfWidth": 595, "pdfHeight": 842}),
                party_id=data.party_id
            )

            MetadataService.upload_sign_metadata(email, data, metadata)

            await SignatureHandler.complete_party_signature(email=email, user_email=user_email, data=data, doc=data.client_info, signed_pdf_base64=signed_pdf_base64, metadata=metadata, file_name=file_name)

            metadata = MetadataService.load_metadata_from_s3(email, data.tracking_id, data.document_id)
            MetadataService.save_metadata_to_s3(email, data.document_id, data.tracking_id, metadata)

            logger.info(f"Final tracking status: {metadata.get('tracking_status', {}).get('status', 'unknown')}")


            return {
                "status": metadata.get("tracking_status", {}).get("status", "unknown"),
                "message": "Signature processed and metadata updated",
                "document_id": data.document_id,
                "tracking_id": data.tracking_id,
                "signed": True
            }

        except Exception as e:
            logger.exception(f"[sign_field] Failed to process signature for document {data.document_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to process signature")

    @staticmethod
    def get_parties_signatures_with_type(data):
        party_signature_map = {}

        # Filter only signature fields
        signature_fields = [
            f for f in data.get("fields", [])
            if f.get("type") == "signature"
        ]

        # Sort so that typed signatures appear last for each party
        # Sorting priority:
        #   1. partyId (numeric)
        #   2. page
        #   3. width
        #   4. height
        #   5. style priority (typed last)
        signature_fields.sort(
            key=lambda f: (
                int(f.get("partyId", 0)),
                f.get("page", 0),
                f.get("width", 0),
                f.get("height", 0),
                f.get("style", "").lower() != "typed"
            )
        )

        for field in signature_fields:
            party_id = field.get("partyId")
            if not party_id:
                continue

            style = field.get("style", "").lower()
            b64_signature = None

            if style == "drawn":
                b64_signature = field.get("value", None)
            elif style == "typed":
                text = field.get("value", "")
                font_name = field.get("font", "DancingScript")  # default fallback
                try:
                    b64_signature = generate_signature_b64_from_fontname(text, font_name)
                except Exception:
                    b64_signature = None
            else:
                continue  # skip unknown styles

            if b64_signature:
                # Always overwrite so last sorted (typed preferred) wins
                party_signature_map[party_id] = {
                    "b64_signature": b64_signature,
                    "style": style,
                    "page": field.get("page"),
                    "width": field.get("width"),
                    "height": field.get("height")
                }

        return party_signature_map

    @staticmethod
    async def complete_party_signature(
            email: str,
            user_email: str,
            data: SignField,
            doc: ClientInfo,
            signed_pdf_base64: str,
            metadata: dict,
            file_name: str
    ):
        try:
            logger.info(
                f"[complete_party_signature] Initiated for email={email}, document_id={data.document_id}, "
                f"tracking_id={data.tracking_id}, party_id={data.party_id}"
            )

            # Load tracking and document metadata
            trackingService = TrackingService(email)
            tracking = load_tracking_metadata(email, data.document_id, data.tracking_id)
            document_summary = load_document_metadata(email, data.document_id)
            logger.debug(f"[complete_party_signature] Loaded metadata for tracking_id={data.tracking_id}")

            email_response, parties, remainder, _, validityDate = trackingService.get_tracking_fields(
                data.document_id, data.tracking_id
            )

            if not email_response or not validityDate:
                raise HTTPException(status_code=400, detail="Missing email response or validity date in metadata")

            # Ensure email responses are objects
            email_response = [EmailResponse(**e) if isinstance(e, dict) else e for e in email_response]

            current_time = datetime.now(timezone.utc).isoformat()
            context_data = {
                "ip": doc.ip,
                "browser": doc.browser,
                "os": doc.os,
                "device": doc.device,
                "location": {
                    "city": doc.city,
                    "region": doc.region,
                    "country": doc.country,
                    "timestamp": doc.timestamp,
                    "timezone": doc.timezone
                }
            }

            # Locate current party
            current_party = next((p for p in tracking.get("parties", []) if str(p.get("id")) == str(data.party_id)),
                                 None)
            if not current_party:
                raise HTTPException(status_code=404, detail="Party ID not found")

            # Ensure 'status' exists
            current_party.setdefault("status", {})

            # ✅ Ensure 'signed' is a list
            if not isinstance(current_party["status"].get("signed"), list):
                current_party["status"]["signed"] = []

            # Append signed entry
            current_party["status"]["signed"].append({
                "isSigned": True,
                "dateTime": current_time,
                **context_data
            })
            logger.info(f"[complete_party_signature] Party {data.party_id} marked as signed")

            if not signed_pdf_base64:
                raise HTTPException(status_code=400, detail="Missing signed PDF data")

            # Decode PDF
            pdf_bytes = SignatureHandler.decode_base64_with_padding(signed_pdf_base64)

            # Check if all parties have signed
            all_signed = all(
                any(s.get("isSigned") for s in p.get("status", {}).get("signed", []))
                for p in tracking.get("parties", [])
            )

            # Update tracking status
            tracking["tracking_status"] = {
                "status": "completed" if all_signed else "in_progress",
                "dateTime": current_time,
                **context_data
            }

            if all_signed:
                # ✅ All parties signed: generate certificate, upload, and send PDFs
                try:
                    signdata = MetadataService.load_metadata_from_s3(email, data.tracking_id, data.document_id)
                    NotificationService().store_notification(
                        email=email,
                        user_email=user_email,
                        document_id=data.document_id,
                        tracking_id=data.tracking_id,
                        document_name=file_name,
                        parties_status=tracking["parties"],
                        timestamp=current_time
                    )

                    document_name = get_document_name(email, data.document_id)

                    # Last sent timestamp
                    first_party_sent = tracking["parties"][0].get("status", {}).get("sent", [])
                    sent_at = first_party_sent[-1]["dateTime"] if first_party_sent else "-"

                    page_count = count_pages_from_base64_pdf(signed_pdf_base64)
                    recipients = []

                    # Get all parties' signatures
                    signatures = SignatureHandler.get_parties_signatures_with_type(signdata)

                    for p in tracking.get("parties", []):
                        party_id = str(p.get("id"))
                        sig_data = signatures.get(party_id, {"b64_signature": None, "style": "-"})
                        signature_style = sig_data["style"]
                        b64_signature = sig_data["b64_signature"]

                        signature_type = {
                            "typed": "Pre-Selected Signature",
                            "uploaded": "Uploaded Signature",
                            "drawn": "Drawn Signature"
                        }.get(signature_style, "No Signature Required")

                        # Last timestamps from lists
                        sent_time = p.get("status", {}).get("sent", [])
                        opened_time = p.get("status", {}).get("opened", [])
                        signed_time = p.get("status", {}).get("signed", [])

                        recipients.append({
                            "name": p["name"],
                            "email": p["email"],
                            "ip_address": signed_time[-1]["ip"] if signed_time else "",
                            "device": f"{signed_time[-1]['browser']} via {signed_time[-1]['os']}" if signed_time else "",
                            "signature_type": signature_type,
                            "sent_time": await format_user_datetime(user_email,
                                                                    sent_time[-1]["dateTime"] if sent_time else "-"),
                            "opened_time": await format_user_datetime(user_email, opened_time[-1][
                                "dateTime"] if opened_time else "-"),
                            "signed_time": await format_user_datetime(user_email, signed_time[-1][
                                "dateTime"] if signed_time else "-"),
                            "authentication": "Email, OTP",
                            "consent": "Accepted",
                            "sign_path": b64_signature or "N/A"
                        })

                    # Generate certificate PDF
                    holder = tracking.get("holder", {})
                    certificate_data = {
                        "title": "Signed PDF",
                        "heading": "Certificate of Completion",
                        "logo_path": get_base64_logo("./images/doculan-logo.png"),
                        "tracking_id": data.tracking_id,
                        "document_name": document_name,
                        "type": "Digital Signature",
                        "status": "Completed",
                        "page_count": page_count,
                        "signer_count": len(tracking["parties"]),
                        "sent_at": await format_user_datetime(user_email, sent_at),
                        "completed_at": await format_user_datetime(user_email, current_time),
                        "signing_order": "Enabled",
                        "hash": certificate_service.compute_sha256(pdf_bytes),
                        "signer": user_email,
                        "recipients": recipients,
                        "generated_at": await format_user_datetime(user_email, datetime.now().strftime("%Y-%m-%dT%H:%M:%S")),
                        "timestamp": await format_user_datetime(user_email, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        "holder": {
                            "name": holder.get("name"),
                            "email": holder.get("email"),
                            "address": format_holder_address(holder.get("address")) if holder.get("address") else "-"
                        }
                    }

                    certificate_pdf_bytes = certificate_service.render_certificate_pdf(certificate_data)
                    certificate_bytes = await PDFSigner().sign_pdf_with_user_cert(email, certificate_pdf_bytes,
                                                                                  data.tracking_id)
                    await upload_file(email, certificate_bytes, data.document_id, data.tracking_id)
                    logger.info("✅ Certificate PDF generated and uploaded")

                    # Send final PDFs
                    document_name = await get_file_name(email, data.document_id)
                    email_service = EmailService()
                    for p in tracking.get("parties", []):
                        recipient_email = p.get("email")
                        if recipient_email:
                            holder = tracking.get("holder", {})
                            holder_name = holder.get("name")
                            holder_email = holder.get("email")
                            await email_service.send_signed_pdf_email(document_name, holder_name, holder_email,
                                                                      recipient_email, pdf_bytes, email_response)
                            logger.info(f"[complete_party_signature] Final signed PDF sent to: {recipient_email}")

                except Exception as e:
                    logger.exception(
                        f"[complete_party_signature] Certificate generation or final PDF sending failed: {e}")


            else:

                # Not all signed: trigger next party

                current_index = next(

                    (i for i, p in enumerate(tracking["parties"]) if str(p.get("id")) == str(data.party_id)), None)

                if current_index is not None and current_index + 1 < len(tracking["parties"]):

                    next_party = tracking["parties"][current_index + 1]

                    next_party.setdefault("status", {})

                    # ✅ Ensure 'sent' is a list

                    if not isinstance(next_party["status"].get("sent"), list):
                        next_party["status"]["sent"] = []

                    next_party["status"]["sent"].append({

                        "isSent": True,

                        "dateTime": current_time,

                        **context_data

                    })

                    logger.info(f"[complete_party_signature] Next party {next_party['id']} marked as sent")

                    cc_emails = next_party.get("cc_emails") or tracking.get("cc_emails")

                    holder = tracking.get("holder", {})

                    await SignatureHandler.initiate_next_party(

                        email=email,

                        user_email=user_email,

                        next_party=next_party,

                        email_response=email_response,

                        validityDate=validityDate,

                        remainder=remainder,

                        data=data,

                        cc_emails=cc_emails,

                        holder=holder

                    )

                    logger.debug(f"[complete_party_signature] initiate_next_party triggered for {next_party['id']}")

                # Save updated tracking and document summary

            save_tracking_metadata(email, data.document_id, data.tracking_id, tracking)

            logger.debug(f"[complete_party_signature] Tracking metadata saved for tracking_id={data.tracking_id}")

            document_summary.setdefault("trackings", {})

            document_summary["trackings"][data.tracking_id] = {

                "status": tracking["tracking_status"]["status"],

                "updated_at": current_time

            }

            document_summary["summary"] = generate_summary_from_trackings(document_summary["trackings"])

            store_status(data.document_id, document_summary, email)

            logger.info(f"[complete_party_signature] Document summary updated for document_id={data.document_id}")

            # Async background update for counts

            threading.Thread(target=update_tracking_status_counts_in_place, args=(email,)).start()

            logger.debug("[complete_party_signature] Background update task triggered for tracking status counts.")


        except Exception as e:

            logger.exception(f"[complete_party_signature] Failed to complete signature: {e}")

            raise HTTPException(status_code=500, detail="Failed to complete signature")

    @staticmethod
    async def initiate_next_party(email,user_email, next_party: Dict[str, Any], email_response: List[EmailResponse], validityDate: str, remainder: int, data: SignField, cc_emails, holder):

        GlobalAuditService.log_document_action(
            email=email,
            document_id=data.document_id,
            action="NEXT_PARTY_INITIATED",
            actor={"email": email},
            targets=[{"email": next_party["email"], "party_id": next_party["id"]}],
            metadata={"tracking_id": data.tracking_id}
        )

        token_data  = await create_signature_token(
            sent_email=next_party["email"],
            tracking_id=data.tracking_id,
            party_id=next_party["id"],
            email=user_email,
            document_id=data.document_id,
            validity_date_str=validityDate,
            remainder_days=remainder
        )
        token = token_data["token"]
        validity_datetime = token_data["validity_datetime"]

        holder_name = holder.get("name")
        holder_email = holder.get("email")
        await email_service.send_link(
            reply_name=holder_name,
            reply_email=holder_email,
            recipient_email=next_party["email"],
            document_id=data.document_id,
            tracking_id=data.tracking_id,
            party_id=next_party["id"],
            party_name=next_party["name"],
            token=token,
            email_response=email_response,
            validity_datetime=validity_datetime,
            cc_emails=cc_emails
        )
        logger.info(cc_emails)

        await document_tracking_manager.log_action(email, data.document_id, data.tracking_id, "INITIATED", data.client_info, next_party["id"])


    @staticmethod
    def check_all_signed(email: str, parties: List[Dict[str, Any]], document_id: str, tracking_id: str):
        if all(party.get("status", {}).get("signed", {}).get("isSigned", False) for party in parties):
            logger.info(f"All parties signed. Marking document {document_id} and tracking {tracking_id} as completed.")

            # Log audit action
            GlobalAuditService.log_document_action(
                email=email,
                document_id=document_id,
                action="DOCUMENT_COMPLETED",
                actor={"email": email},
                metadata={"tracking_id": tracking_id}
            )

            # Load all document-level metadata entries
            try:
                all_doc_entries = load_all_json_from_prefix(email)
                all_docs = {entry["document_id"]: entry for entry in all_doc_entries if "document_id" in entry}
            except Exception as e:
                logger.warning(f"Failed to load S3 metadata summary for {email}: {str(e)}")
                all_docs = {}

            if document_id in all_docs:
                doc_entry = all_docs[document_id]
                trackings = doc_entry.get("trackings", {})

                if tracking_id in trackings:
                    trackings[tracking_id]["tracking_status"] = "completed"
                    trackings[tracking_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

                    doc_entry["trackings"] = trackings
                    doc_entry["summary"] = generate_summary_from_trackings(trackings)
                    all_docs[document_id] = doc_entry

                    try:
                        # Save updated metadata back to S3
                        store_tracking_status(doc_entry, document_id, email)
                        logger.info(
                            f"Updated metadata for document {document_id}, tracking {tracking_id} marked as completed.")
                    except Exception as e:
                        logger.error(f"Failed to write S3 metadata for {document_id}: {e}")



    @staticmethod
    def decode_base64_with_padding(b64_string: str) -> bytes:
        b64_string = b64_string.strip().replace('\n', '').replace('\r', '')
        missing_padding = len(b64_string) % 4
        if missing_padding:
            b64_string += '=' * (4 - missing_padding)
        return base64.b64decode(b64_string)
    @staticmethod
    def normalize_signed(status: Dict[str, Any], field: str) -> List[Dict[str, Any]]:
        """
        Normalize a given status field (e.g., 'signed', 'sent', 'opened')
        so it always returns a list of dicts.
        Handles old/corrupt formats safely.
        """
        if not isinstance(status, dict):
            return []

        entries = status.get(field, [])

        # Case: dict → wrap into list
        if isinstance(entries, dict):
            return [entries]

        # Case: list → keep only dicts
        if isinstance(entries, list):
            return [e for e in entries if isinstance(e, dict)]

        # Case: missing or invalid type → return empty
        return []

    @staticmethod
    async def get_party_initiate_resend(document_id: str, user_email: str, email: str, email_response: List[EmailResponse],
                                  parties: List[Dict[str, Any]], remainder: int, data: ClientInfo, tracking: Dict[str, Any],
                                  tracking_id: str, validityDate: str) -> str:
        for party in parties:
            party_id = party.get("id")
            party_name = party.get("name")
            party_email = party.get("email")
            if not party_id or not party_email:
                continue

            party_entry = next((p for p in tracking.get("parties", []) if p.get("id") == party_id), None)
            if not party_entry:
                continue

            status = party_entry.get("status", {})

            # Always safe, always a list of dicts
            signed_entries = SignatureHandler.normalize_signed(status, "signed")
            # ✅ This is the first unsigned party (current party)
            if any(s.get("isSigned") for s in signed_entries):
                continue

            try:
                GlobalAuditService.log_document_action(
                    email=email,
                    document_id=document_id,
                    action="RESEND_LINK",
                    actor={"email": email},
                    targets=[{"email": party_email, "party_id": party_id}],
                    metadata={"tracking_id": tracking_id}
                )

                token_data  = await create_signature_token(
                    sent_email=party_email,
                    tracking_id=tracking_id,
                    party_id=party_id,
                    email=user_email,
                    document_id=document_id,
                    validity_date_str=validityDate,
                    remainder_days=remainder
                )
                token = token_data["token"]
                validity_datetime = token_data["validity_datetime"]
                holder = tracking.get("holder", {})
                holder_name = holder.get("name")
                holder_email = holder.get("email")
                await email_service.send_link(
                    reply_name=holder_name,
                    reply_email=holder_email,
                    recipient_email=party_email,
                    document_id=document_id,
                    tracking_id=tracking_id,
                    party_id=party_id,
                    party_name=party_name,
                    token=token,
                    email_response=email_response,
                    validity_datetime=validity_datetime,
                    cc_emails=tracking.get("cc_emails")
                )

                await document_tracking_manager.log_action(
                    email=email,
                    document_id=document_id,
                    tracking_id=tracking_id,
                    action="RE-INITIATED",
                    data=data,
                    party_id=party_id,
                )

                return validityDate

            except Exception as e:
                logger.exception(f"Failed to resend to current party_id={party_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Resend failed for current party: {party_id}")

        # ❌ No eligible party found
        raise HTTPException(status_code=400, detail="No eligible unsigned party to resend")

    @staticmethod
    async def initiate_resend(data: DocumentResendRequest, email: str, user_email: str):
        global validityDate
        trackingService = TrackingService(email)
        tracking_id = data.tracking_id
        document_id = data.document_id
        email_response, parties, remainder, tracking, validity_Date = trackingService.get_tracking_fields(
            data.document_id, data.tracking_id)

        tracking_status = tracking.get("tracking_status")
        logger.info(tracking_status)
        status = tracking_status.get("status")
        logger.info(status)
        if status == "expired" or "in_progress":
            if data.validityDate:
                validityDate = data.validityDate
            else:
                validityDate = validity_Date

            remainder = data.remainder

        if not email_response or not validityDate:
            raise HTTPException(status_code=400, detail="Missing email response or validity date in metadata")

        email_response = [EmailResponse(**e) if isinstance(e, dict) else e for e in email_response]

        last_validity_date = await SignatureHandler.get_party_initiate_resend(
            document_id=document_id,
            user_email=user_email,
            email=email,
            email_response=email_response,
            parties=parties,
            remainder=remainder,
            data=data.client_info,
            tracking=tracking,
            tracking_id=tracking_id,
            validityDate=validityDate
        )
        doc = data.client_info
        current_time = datetime.now(timezone.utc).isoformat()
        metadata = MetadataService.get_metadata(email, data.tracking_id, data.document_id)
        context_data = {
            "ip": doc.ip,
            "browser": doc.browser,
            "os": doc.os,
            "device": doc.device,
            "location": {
                "city": doc.city,
                "region": doc.region,
                "country": doc.country,
                "timestamp": doc.timestamp,
                "timezone": doc.timezone
            }
        }
        metadata["validityDate"] = validityDate
        tracking["tracking_status"] = {
            "status": "in_progress",
            "dateTime": current_time,
            **context_data
        }
        MetadataService.save_metadata_to_s3(email, data.document_id, data.tracking_id, metadata)

        return {
            "message": "Resend initiated",
            "tracking_id": tracking_id,
            "new_validityDate": last_validity_date
        }

    @staticmethod
    async def initiate_remainder(document_id, tracking_id, email: str, user_email: str):
        trackingService = TrackingService(email)
        email_response, parties, remainder, tracking, validityDate = trackingService.get_tracking_fields(
            document_id, tracking_id
        )
        tracking_status = tracking.get("tracking_status", {})
        status = tracking_status.get("status")


        # ✅ Skip reminder if terminal state
        if status in ["completed", "expired", "declined", "cancelled"]:
            await db["scheduled_jobs"].update_one(
                {"document_id": document_id, "tracking_id": tracking_id},
                {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
            )
            return {
                "message": f"Reminder skipped, document is already {status}",
                "tracking_id": tracking_id,
                "status": status,
            }

        if not email_response or not validityDate:
            raise HTTPException(
                status_code=400,
                detail="Missing email response or validity date in metadata",
            )

        email_response = [
            EmailResponse(**e) if isinstance(e, dict) else e for e in email_response
        ]

        # continue normal resend flow
        last_validity_date = await SignatureHandler.get_party_initiate_remainder(
            document_id=document_id,
            user_email=user_email,
            email=email,
            email_response=email_response,
            parties=parties,
            remainder=remainder,
            tracking=tracking,
            tracking_id=tracking_id,
            validityDate=validityDate,
        )

        current_time = datetime.now(timezone.utc).isoformat()
        metadata = MetadataService.get_metadata(email, tracking_id, document_id)

        # System context since this is automated resend
        context_data = {
            "ip": "System",
            "browser": "System",
            "os": "System",
            "device": "System",
            "location": {
                "city": "System",
                "region": "System",
                "country": "System",
                "timestamp": "System",
                "timezone": "System",
            },
        }

        metadata["validityDate"] = validityDate
        tracking["tracking_status"] = {
            "status": "in_progress",
            "dateTime": current_time,
            **context_data,
        }

        MetadataService.save_metadata_to_s3(email, document_id, tracking_id, metadata)

        await db["documents"].update_one(
            {"document_id": document_id, "tracking_id": tracking_id},
            {"$set": {"status": "in_progress", "updated_at": datetime.now(timezone.utc)}},
        )

        return {
            "message": "Resend initiated",
            "tracking_id": tracking_id,
            "new_validityDate": last_validity_date,
        }

    @staticmethod
    async def get_party_initiate_remainder(document_id: str, user_email: str, email: str,
                                           email_response: List[EmailResponse],
                                           parties: List[Dict[str, Any]], remainder: int,
                                           tracking: Dict[str, Any],
                                           tracking_id: str, validityDate: str) -> str:
        for party in parties:
            party_id = party.get("id")
            party_name = party.get("name")
            party_email = party.get("email")
            if not party_id or not party_email:
                continue

            party_entry = next((p for p in tracking.get("parties", []) if p.get("id") == party_id), None)
            if not party_entry:
                continue

            # ✅ Skip signed parties
            if party_entry.get("status", {}).get("signed") is True:
                continue

            # ✅ First unsigned party found → send reminder
            try:
                GlobalAuditService.log_document_action(
                    email=email,
                    document_id=document_id,
                    action="RESEND_LINK",
                    actor={"email": email},
                    targets=[{"email": party_email, "party_id": party_id}],
                    metadata={"tracking_id": tracking_id}
                )

                token_data = await create_signature_token(
                    sent_email=party_email,
                    tracking_id=tracking_id,
                    party_id=party_id,
                    email=user_email,
                    document_id=document_id,
                    validity_date_str=validityDate,
                    remainder_days=remainder
                )
                token = token_data["token"]
                validity_datetime = token_data["validity_datetime"]
                holder = tracking.get("holder", {})

                await email_service.send_link(
                    reply_name=holder.get("name"),
                    reply_email=holder.get("email"),
                    recipient_email=party_email,
                    document_id=document_id,
                    tracking_id=tracking_id,
                    party_id=party_id,
                    party_name=party_name,
                    token=token,
                    email_response=email_response,
                    validity_datetime=validity_datetime,
                    cc_emails=tracking.get("cc_emails")
                )

                # Log remainder action
                client_info = ClientInfo(
                    ip="System",
                    browser="System",
                    os="System",
                    device="System",
                    city="System",
                    region="System",
                    country="System",
                    timestamp="System",
                    timezone="System"
                )
                await document_tracking_manager.log_action(
                    email=email,
                    document_id=document_id,
                    tracking_id=tracking_id,
                    action="REMAINDER",
                    data=client_info,
                    party_id=party_id,
                )

                return validityDate

            except Exception as e:
                logger.exception(f"Failed to resend to party_id={party_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Resend failed for party: {party_id}")

        raise HTTPException(status_code=400, detail="No eligible unsigned party to resend")

