import json
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from pydantic import ValidationError

from app.model.form_model import FormModel
from app.schemas.form_schema import EmailResponse, FormRequest, FormSubmissionRequest, ResendFormRequest
from app.services.email_service import email_service
from app.services.notification_service import NotificationService
from app.services.pdf_service import PDFGenerator
from config import config
from database.db_config import s3_client
from repositories import s3_repo
from repositories.form_repository import FormRepository
from fastapi import HTTPException, status
from typing import Dict, List

from utils.logger import logger


class FormService:

    @staticmethod
    def create_form(form_id: str, form_data: dict, email: str, current_user: dict, user_email):
        created_at = datetime.now(timezone.utc).isoformat()
        form_data["created_at"] = created_at
        form_data["created_by"] = {
            "name": current_user.get("name"),
            "email": user_email
        }
        result = FormRepository.create_form(form_id, form_data, email)
        return result

    @staticmethod
    def get_form(form_id: str, email: str):
        form = FormRepository.read_form(form_id, email)
        return form

    @staticmethod
    def get_all_forms(email: str):
        forms = FormRepository.get_all_forms(email)
        return forms

    @staticmethod
    def update_form(form_id: str, updated_data: dict, email: str):
        result = FormRepository.update_form(form_id, updated_data, email)
        return result

    @staticmethod
    def delete_form(form_id: str, email: str):
        result = FormRepository.delete_form(form_id, email)
        return result

    @staticmethod
    def update_tracking(form_id: str, new_entry: dict, party_email: str, email: str):
        FormRepository.update_trackings(email, form_id, party_email, new_entry)

    @staticmethod
    def get_tracking_entry(form_id: str, party_email: str, email: str) -> dict:
        tracking = FormRepository.get_tracking(email, form_id, party_email)
        return tracking

    @staticmethod
    def validate_submission(form, values):
        FormRepository.validate_form(form, values)

    @staticmethod
    async def upload_pdf_to_s3(pdf_bytes: bytes, form_id: str, email: str, party_email: str, form_path, formTitle) -> str:
        result = await FormRepository.upload_pdf(email=email, form_id=form_id, party_email=party_email, pdf_bytes=pdf_bytes, form_path=form_path, formTitle=formTitle)
        return result

    async def get_pdf_to_s3(self, email: str, form_id: str, party_email: str):
        form = self.get_form(form_id, email)
        pdf = await FormRepository.get_pdf(email, form_id, party_email, form)
        return pdf

    async def get_forms(self, email, submission):
        logger.info(f"Form submission started for form_id={submission.form_id} by user={email}")
        form = self.get_form(submission.form_id, email)
        return form


    async def validate_form(self, form, submission):
        self.validate_submission(form, submission.values)


    async def submit(self, email, submission: FormSubmissionRequest, user_email):
        form = await self.get_forms(email, submission)
        await self.validate_form(form, submission)

        pdfGenerator = PDFGenerator()
        pdf_bytes = await pdfGenerator.generate_pdf(email, form, submission)

        form_path = form.get("formPath")
        formTitle = form.get("formTitle")

        try:
            await self.upload_pdf_to_s3(
                pdf_bytes=pdf_bytes,
                form_id=submission.form_id,
                email=email,
                party_email=submission.party_email,
                form_path=form_path,
                formTitle=formTitle,
            )

            # Update status with 'completed' timestamp on submission
            timestamp = datetime.utcnow().isoformat() + "Z"
            client_info_dict = submission.client_info.dict() if submission.client_info else {}

            new_status_updates = {
                "completed": {
                    "timestamp": timestamp,
                    "client_info": client_info_dict
                }
            }

            data = FormModel.upload_submission(
                email=email,
                form_id=submission.form_id,
                party_email=submission.party_email,
                new_status_updates=new_status_updates,
                submitted_values=submission.values
            )
            party_name = data.get("party_name", "-")
            await NotificationService.store_form_notification(email, user_email, submission.form_id, formTitle, submission.party_email, timestamp, party_name)


            holder = data.get("holder", {})
            cc_emails = data.get("cc_emails", [])

            email_service.send_filled_pdf_email(
                to_email=submission.party_email,
                pdf_bytes=pdf_bytes,
                reply_name=holder.get("name"),
                reply_email=holder.get("email"),
                cc_emails=cc_emails
            )


        except Exception as e:
            logger.error(f"Failed to process party {submission.party_email}: {str(e)}")

        # self.audit_trail(
        #     email,
        #     submission.form_id,
        #     "FORM_SUBMITTED",
        #     {"party_email": submission.party_email}
        # )

        return {
            "message": "Form submitted and PDF sent successfully",
            "form_id": submission.form_id,
            "party_email": submission.party_email
        }

    async def form_tracking_payload(self, data: FormRequest, email):
        stored_form = self.get_form(data.form_id, email)
        form_title = stored_form.get("formTitle")
        form_fields = stored_form.get("fields", [])
        created_at=stored_form.get("created_at")
        # Build tracking entries keyed by party_email
        parties_tracking_entries = []
        for party in data.parties:
            tracking_entry = {
                "party_email": party.email,
                "party_name":party.name,
                "party_id": party.party_id,
                "status":"sent",
                "form_title": form_title,
                "validityDate": data.validityDate,
                "remainder": data.remainder,
                "email_responses":data.email_responses,
                "holder":data.holder,
                "cc_emails":data.cc_emails,
                "created_at":created_at,
                "fields": form_fields,
                "client_info": data.client_info
            }
            parties_tracking_entries.append(tracking_entry)

        return parties_tracking_entries

    async def send_forms(self, data:FormRequest, email, user_email):
        from auth_app.app.utils.security import create_form_token

        try:
            parties_tracking_entries = await self.form_tracking_payload(data, email)

            for tracking_entry in parties_tracking_entries:
                party_email = tracking_entry["party_email"]
                party_id = tracking_entry["party_id"]
                party_name = tracking_entry["party_name"]
                self.update_tracking(data.form_id, tracking_entry, party_email, email)

                try:
                    token_data = await create_form_token(
                        sent_email=party_email,
                        party_id=party_id,
                        email=user_email,
                        form_id=data.form_id,
                        validity_date_str=data.validityDate,
                        remainder_days=data.remainder,
                    )
                    logger.info(f"{token_data}")
                    token = token_data["token"]
                    validity_datetime = token_data["validity_datetime"]
                    email_resp = data.email_responses[0]

                    await email_service.send_form_link(
                        recipient_email=party_email,
                        form_id=data.form_id,
                        party_id=party_id,
                        party_name = party_name,
                        token=token,
                        email_response=email_resp,
                        validity_datetime=validity_datetime,
                        reply_name=data.holder.name if data.holder else None,
                        reply_email=data.holder.email if data.holder else None,
                        cc_emails=data.cc_emails
                    )

                    # FormRepository.update_tracking_status(
                    #     email, data.form_id, party_email,  "Sent",request
                    # )
                except Exception as email_error:
                    logger.error(f"Failed to send email to {party_email}: {str(email_error)}")

            # self.audit_trail(email, data.form_id, "FORM_SENT",
            #                  {"parties": [p["party_email"] for p in parties_tracking_entries]})

            return {
                "message": "Form sent and tracking updated successfully",
                "tracked_parties": [p["party_email"] for p in parties_tracking_entries],
                "form_id": data.form_id,
            }

        except Exception as e:
            logger.error(f"Error in send_form for form_id={data.form_id}, user={email}: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal error: {str(e)}")


        except Exception as e:
            logger.error(f"Error in send_form for form_id={data.form_id}, user={email}: {str(e)}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal error: {str(e)}")


    async def resend_form(
            self,
            data: ResendFormRequest,
            form_id: str,
            party_email: str,
            email: str,
            user_email: str
    ):
        from auth_app.app.utils.security import create_form_token

        track_key = f"{email}/forms/submissions/{form_id}/trackings.json"

        try:
            # --- Load trackings.json ---
            try:
                resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=track_key)
                tracking_data = json.loads(resp['Body'].read().decode('utf-8'))
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    raise HTTPException(status_code=404, detail="Tracking file not found")
                else:
                    raise

            # Locate party entry
            if party_email not in tracking_data:
                raise HTTPException(status_code=404, detail="Party not found in tracking")

            party_data = tracking_data[party_email]

            # --- Block resend if status is terminal ---
            terminal_statuses = {"completed", "declined", "cancelled"}
            party_status = party_data.get("status", {}).get("state")

            if party_status in terminal_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot resend form. Party status is '{party_status}'."
                )

            # --- Generate new token ---
            validity_date_str = party_data.get("validityDate")
            if data.validityDate:
                validity_date_str = data.validityDate

            logger.info(f"[RESEND] Using validity_date_str={validity_date_str} for party={party_email}")

            token_data = await create_form_token(
                sent_email=party_email,
                party_id=party_data.get("party_id"),
                email=user_email,
                form_id=form_id,
                validity_date_str=validity_date_str,
                remainder_days=party_data.get("remainder", 1),
            )
            token = token_data["token"]
            validity_datetime = token_data["validity_datetime"]

            logger.info(f"[RESEND] Generated token={token} validity_datetime={validity_datetime} "
                        f"type={type(validity_datetime)} for {party_email}")

            # --- Ensure datetime object ---
            if isinstance(validity_datetime, str):
                try:
                    validity_datetime = datetime.fromisoformat(validity_datetime.replace("Z", ""))
                    logger.warning(f"[RESEND] Converted validity_datetime string to datetime for {party_email}")
                except Exception as conv_err:
                    logger.error(f"[RESEND] Failed to parse validity_datetime='{validity_datetime}' "
                                 f"for {party_email}: {conv_err}")
                    raise HTTPException(status_code=500, detail="Invalid validity date format")

            # --- Prepare new resend log entry ---
            resend_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "client_info": data.client_info.dict() if data.client_info else {},
                "token": token,
                "valid_until": validity_datetime.isoformat() + "Z",
            }
            logger.info(f"[RESEND] Created resend_entry={resend_entry}")

            # --- Update tracking metadata ---
            status = party_data.get("status", {})
            resent_logs = party_data.get("resent_logs", [])
            resent_logs.append(resend_entry)

            party_data.update({
                "status": status,
                "resent_logs": resent_logs,  # keep history
                "resent_count": party_data.get("resent_count", 0) + 1,
                "last_token": token,
            })
            tracking_data[party_email] = party_data

            # --- Save back to S3 ---
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=track_key,
                Body=json.dumps(tracking_data, indent=2).encode("utf-8"),
                ContentType="application/json"
            )

            # --- Resend email ---
            email_responses = party_data.get("email_responses", [])
            if email_responses and isinstance(email_responses, list):
                try:
                    email_response_obj = EmailResponse(**email_responses[0])
                    await email_service.send_form_link(
                        recipient_email=party_email,
                        form_id=form_id,
                        party_id=party_data.get("party_id"),
                        party_name=party_data.get("party_name"),
                        token=token,
                        email_response=email_response_obj,
                        validity_datetime=validity_datetime,
                        reply_name=party_data.get("holder", {}).get("name"),
                        reply_email=party_data.get("holder", {}).get("email"),
                        cc_emails=party_data.get("cc_emails", []),
                    )
                except ValidationError as ve:
                    logger.error(f"Invalid email_response for {party_email}: {ve}")
            else:
                logger.error(f"No valid email_response found for {party_email}")

            return {
                "message": "Form link resent successfully",
                "party_email": party_email,
                "form_id": form_id,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error while resending form: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to resend form")


    @staticmethod
    def get_party_submitted_values(email: str, form_id: str, party_email: str) -> dict:
        """
        Business logic: fetch user data from repository and extract values for a party.
        """
        user_data = FormRepository.get_user_data(email, form_id)

        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Form submission data not found"
            )

        submitted_values = user_data.get(party_email)
        if not submitted_values:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No submitted values found for party_email: {party_email}"
            )

        return {
            "form_id": form_id,
            "party_email": party_email,
            "submitted_values": submitted_values,
        }

    @staticmethod
    async def get_all_statuses(email: str, form_id: str) -> dict:
        """
        Business logic: Extract statuses for all parties in a form.
        """
        tracking_data = await FormRepository.get_tracking_data(email, form_id)

        if not tracking_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission data not found"
            )

        statuses = {
            party_email: party_data.get("status", {})
            for party_email, party_data in tracking_data.items()
        }

        return {"form_id": form_id, "statuses": statuses}

    @staticmethod
    def count_statuses(statuses: list[dict]) -> dict:
        counts = {"sent": 0, "opened": 0, "completed": 0, "cancelled": 0}

        for status in statuses:
            if not isinstance(status, dict):
                continue

            last_status, last_timestamp = None, None

            for key, value in status.items():
                if isinstance(value, list) and value:
                    latest_entry = value[-1]
                    ts = latest_entry.get("timestamp")
                elif isinstance(value, dict):
                    latest_entry = value
                    ts = latest_entry.get("timestamp")
                else:
                    continue

                if ts and (last_timestamp is None or ts > last_timestamp):
                    last_timestamp = ts
                    last_status = key

            if last_status and last_status in counts:
                counts[last_status] += 1

        return counts

    @staticmethod
    async def get_status_counts(email: str, form_id: str | None = None) -> dict:
        """
        Aggregate status counts across all forms, or a specific form.
        """
        total_counts = {"sent": 0, "opened": 0, "completed": 0, "cancelled": 0}

        if form_id:
            data = await FormRepository.get_tracking_data(email, form_id)
            if not data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Submission data not found"
                )

            statuses = [
                party_data.get("status", {}) if isinstance(party_data, dict) else {}
                for party_data in data.values()
            ]
            return {"form_id": form_id, "status_counts": FormService.count_statuses(statuses)}

        # Aggregate across all forms
        form_folders = FormRepository.list_form_folders(email)
        for folder in form_folders:
            form_id_from_path = folder.split("/")[-2]  # extract {form_id} from prefix
            data = await FormRepository.get_tracking_data(email, form_id_from_path)
            if not data:
                continue

            statuses = [
                party_data.get("status", {}) if isinstance(party_data, dict) else {}
                for party_data in data.values()
            ]
            counts = FormService.count_statuses(statuses)

            for k in total_counts:
                total_counts[k] += counts[k]

        return {"status_counts": total_counts}

    @staticmethod
    def get_tracking_status(tracking: dict) -> str:
        """
        Determine tracking status based on rules.
        """
        status_info = tracking.get("status", {})

        if "completed" in status_info:
            return "completed"
        if "cancelled" in status_info:
            return "cancelled"

        # Expired check
        validity = tracking.get("validityDate")
        if validity:
            try:
                valid_until = datetime.fromisoformat(validity).replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > valid_until:
                    return "expired"
            except Exception:
                pass

        if "opened" in status_info or "sent" in status_info:
            return "in_progress"

        return "unknown"

    @staticmethod
    def get_trackings_status_counts(email: str) -> dict:
        """
        Aggregate tracking status counts across all forms.
        """
        total_status_counts = {
            "in_progress": 0,
            "completed": 0,
            "cancelled": 0,
            "expired": 0,
            "unknown": 0
        }
        forms_data = {}

        try:
            form_folders = FormRepository.list_form_folders(email)

            for folder in form_folders:
                form_id = folder.split("/")[-2]
                trackings = FormRepository.get_trackings(email, form_id)
                if not trackings:
                    continue

                forms_data.setdefault(form_id, {
                    "in_progress": {},
                    "completed": {},
                    "cancelled": {},
                    "expired": {},
                    "unknown": {},
                    "created_at": None,
                    "form_title": None
                })

                # external call to fetch form metadata
                form_meta = FormService.get_form(form_id, email)

                for party_email, tracking in trackings.items():
                    status = FormService.get_tracking_status(tracking)
                    total_status_counts[status] += 1

                    forms_data[form_id][status][party_email] = {
                        "party_name": tracking.get("party_name"),
                        "status": status,
                        "last_updated": tracking.get("status", {})
                    }

                    # Set form-level fields only once
                    if not forms_data[form_id]["created_at"]:
                        forms_data[form_id]["created_at"] = tracking.get("created_at")
                    if not forms_data[form_id]["form_title"]:
                        forms_data[form_id]["form_title"] = form_meta.get("formTitle")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching trackings: {e}")

        return {
            "total_status_counts": total_status_counts,
            "forms": forms_data
        }

    async def get_party_status(self, email: str, form_id: str, party_email: str):
        try:
            data = await FormRepository.get_tracking_data(email, form_id)
            party_data = data.get(party_email)

            if not party_data:
                return None

            return {
                "form_id": form_id,
                "party_email": party_email,
                "party_name": party_data.get("party_name"),
                "status": party_data.get("status", {})
            }

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise HTTPException(status_code=404, detail="Submission data not found")
            raise HTTPException(status_code=500, detail="Failed to fetch submission data")

    async def get_all_submitted_values(self, email: str) -> dict:
        all_submissions = {}
        form_ids = await FormRepository.list_form_ids(email)

        for form_id in form_ids:
            tracking_data = await FormRepository.get_tracking_data(email, form_id)
            user_data = FormRepository.get_user_data(email, form_id)

            merged_data = {}
            party_emails = set(tracking_data.keys()) | set(user_data.keys())

            for party_email in party_emails:
                merged_data[party_email] = {}

                if party_email in tracking_data:
                    merged_data[party_email]["status"] = tracking_data[party_email].get("status", {})
                    merged_data[party_email]["last_updated"] = tracking_data[party_email].get("last_updated")
                    merged_data[party_email]["party_name"] = tracking_data[party_email].get("party_name")

                if party_email in user_data:
                    merged_data[party_email]["submitted_values"] = [
                        {
                            "id": field.get("id"),
                            "type": field.get("type"),
                            "label": field.get("label"),
                            "required": field.get("required"),
                            "sensitive": field.get("sensitive"),
                            "value": field.get("value"),
                        }
                        for field in user_data[party_email]
                    ]

            if merged_data:
                all_submissions[form_id] = merged_data

        return all_submissions



