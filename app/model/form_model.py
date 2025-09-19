import uuid
from botocore.exceptions import ClientError

from app.schemas.form_schema import FormCancelled
from app.services.security_service import AESCipher, EncryptionService
from config import config
from database.db_config import s3_client
from utils.logger import logger
from fastapi import Request, HTTPException
from datetime import datetime, timezone
import requests
from user_agents import parse
import json


class FormModel:

    @staticmethod
    def _get_forms_json(email: str, form_id: str) -> dict:
        try:
            response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=f"{email}/forms/{form_id}.json")
            return json.loads(response["Body"].read().decode("utf-8"))
        except s3_client.exceptions.NoSuchKey:
            return {}
        except Exception as e:
            logger.error(f"Error fetching form {form_id} for {email}: {e}")
            return {}

    @staticmethod
    def _save_forms_json(email: str, form_id: str, data: dict):
        try:
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=f"{email}/forms/{form_id}.json",
                Body=json.dumps(data),
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )
        except Exception as e:
            logger.error(f"Error saving form {form_id} for {email}: {e}")
            raise

    @staticmethod
    def list_forms(email: str):
        prefix = f"{email}/"
        logger.info(f"[list_forms] Listing forms for email={email}, prefix={prefix}")

        try:
            response = s3_client.list_objects_v2(
                Bucket=config.S3_BUCKET,
                Prefix=prefix,
            )
            logger.debug(f"[list_forms] Raw S3 response: {response}")

            form_items = []
            contents = response.get("Contents", [])
            logger.info(f"[list_forms] Found {len(contents)} objects under {prefix}")

            for obj in contents:
                key = obj.get("Key")
                logger.debug(f"[list_forms] Processing object key={key}")

                if key.endswith(".json") and not key.endswith("forms.json"):
                    parts = key.split("/")  # e.g., ["email", "name", "forms", "file.json"]

                    # ✅ Only include if parent folder == "forms" and it's directly under forms
                    if len(parts) >= 3 and parts[-2] == "forms":
                        form_id = parts[-1].replace(".json", "")
                        logger.info(f"[list_forms] Found form_id={form_id} (key={key})")

                        try:
                            form_data = FormModel._get_forms_json(email, form_id)
                            logger.debug(f"[list_forms] Loaded form_data for {form_id}: {form_data}")
                            form_items.append({"formId": form_id, **form_data})
                        except Exception as inner_e:
                            logger.error(f"[list_forms] Failed to load form data for {form_id}: {inner_e}")

            logger.info(f"[list_forms] Returning {len(form_items)} forms for {email}")
            return form_items

        except Exception:
            logger.exception(f"[list_forms] ❌ Failed to list forms for {email}")
            raise HTTPException(status_code=500, detail="Unable to list forms")

    @staticmethod
    def get_form(form_id: str, email: str):
        # Return form data directly (fix from original)
        forms = FormModel._get_forms_json(email, form_id)
        return forms

    @staticmethod
    def save_form(form_id: str, form_data: dict, email: str):
        # Save form JSON file directly
        FormModel._save_forms_json(email, form_id, form_data)

    @staticmethod
    def update_form(form_id: str, updated_data: dict, email: str):
        forms = FormModel._get_forms_json(email, form_id)
        if forms:
            FormModel._save_forms_json(email, form_id, updated_data)
        else:
            raise KeyError(f"Form ID {form_id} does not exist for user {email}.")

    @staticmethod
    def delete_form(form_id: str, email: str):
        # Deleting a form means deleting the JSON file from S3
        key = f"{email}/forms/{form_id}.json"
        try:
            s3_client.delete_object(Bucket=config.S3_BUCKET, Key=key)
        except Exception as e:
            logger.error(f"Failed to delete form {form_id} for {email}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to delete form")

    @staticmethod
    def validate_form_values(form, values):
        missing_fields = []
        field_map = {}
        for field in form.get("fields", []):
            field_map[str(field["id"])] = field
            field_map[field["label"]] = field  # support label key as well
            if field.get("required") and not (
                    str(field["id"]) in values or field["label"] in values
            ):
                missing_fields.append(field["label"])
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing_fields)}",
            )


    @staticmethod
    def get_form_user_data(form_id: str, email: str) -> dict:
        user_data_key = f"{email}/forms/submissions/{form_id}/form_user_data.json"

        try:
            resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=user_data_key)
            form_user_data = json.loads(resp['Body'].read().decode('utf-8'))
            return form_user_data
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # No submissions yet
                return {}
            logger.error(f"Failed to fetch form_user_data.json for {form_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch form user data")
        except Exception as e:
            logger.error(f"Unexpected error while fetching form_user_data.json for {form_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch form user data")

    @staticmethod
    def upload_submission(email: str, form_id: str, party_email: str, new_status_updates: dict,
                          submitted_values: dict = None):
        now_iso = datetime.utcnow().isoformat() + "Z"

        # --- 1. Update trackings.json ---
        tracking_key = f"{email}/forms/submissions/{form_id}/trackings.json"
        try:
            try:
                resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=tracking_key)
                tracking_data = json.loads(resp['Body'].read().decode('utf-8'))
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    tracking_data = {}
                else:
                    raise

            party_tracking = tracking_data.get(party_email, {})
            status = party_tracking.get("status", {})
            status.update(new_status_updates)
            party_tracking["status"] = status
            party_tracking["last_updated"] = now_iso
            tracking_data[party_email] = party_tracking

            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=tracking_key,
                Body=json.dumps(tracking_data, indent=2).encode('utf-8'),
                ContentType='application/json'
            )

            logger.info(f"Updated tracking for {party_email} in form {form_id}")
        except Exception as e:
            logger.error(f"Failed to update tracking.json for {party_email}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update submission tracking")

        # --- 2. Update form_user_data.json ---
        if submitted_values:
            user_data_key = f"{email}/forms/submissions/{form_id}/form_user_data.json"
            try:
                try:
                    resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=user_data_key)
                    form_user_data = json.loads(resp['Body'].read().decode('utf-8'))
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        form_user_data = {}
                    else:
                        raise

                existing_fields = form_user_data.get(party_email, [])

                # Update values where IDs match
                for field in existing_fields:
                    field_id_str = str(field["id"])  # Match string keys from submitted_values
                    if field_id_str in submitted_values:
                        field.update({
                            "value": submitted_values[field_id_str],
                            "id": field.get("id"),
                            "label": field.get("label"),
                            "type": field.get("type"),
                            "required": field.get("required", False),
                            "sensitive": field.get("sensitive", False),
                            "disclaimerText": field.get("disclaimerText", None),
                        })

                logger.info(f"{submitted_values}---{existing_fields}")
                form_user_data[party_email] = existing_fields

                s3_client.put_object(
                    Bucket=config.S3_BUCKET,
                    Key=user_data_key,
                    Body=json.dumps(form_user_data, indent=2).encode('utf-8'),
                    ContentType='application/json'
                )

                logger.info(f"Updated form field values for {party_email} in form {form_id}")
            except Exception as e:
                logger.error(f"Failed to update form_user_data.json for {party_email}: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to update submitted values")

        return tracking_data.get(party_email)

    @staticmethod
    async def upload_pdfs(email, form_id, party_email, pdf_bytes, form_path, formTitle):
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        key = f"{email}/files/{form_path}/{party_email}/{formTitle}-filled.pdf"
        encrypt = cipher.encrypt(pdf_bytes)

        # Upload PDF
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=key,
            Body=encrypt,
            ContentType="application/pdf",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )

        # Create metadata

        document_id = "form-doc-" + str(uuid.uuid4())
        metadata_key = f"{email}/metadata/data/{document_id}.json"
        metadata = {
            "document_id": document_id,
            "fileName": f"{formTitle}-filled.pdf",
            "fileSizeBytes": len(pdf_bytes),
            "contentType": "application/pdf"
        }
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=metadata_key,
            Body=json.dumps(metadata),
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )

        # Update index (optional but recommended)
        index_key = f"{email}/index/document_index.json"
        try:
            response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=index_key)
            index_data = json.loads(response['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchKey:
            index_data = {}
        except Exception as e:
            logger.warning(f"Could not read index: {e}")
            index_data = {}
        user_name = FormModel.get_form_party_name(email, form_id, party_email)

        from datetime import datetime, timezone
        last_modified = datetime.now(timezone.utc).isoformat()
        index_data[document_id] = {
            "file_path": key,
            "metadata_path": metadata_key,
            "fileName": f"{formTitle}-filled.pdf",
            "size": len(pdf_bytes),
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

        return {
            "pdf_key": key,
            "metadata_key": metadata_key
        }

    @staticmethod
    async def get_pdfs(email, form_id, party_email, form):
        form_path = form.get("formPath")
        formTitle = form.get("formTitle")
        key = f"{email}/files/{form_path}/{party_email}/{formTitle}-filled.pdf"

        response = s3_client.get_object(
            Bucket=config.S3_BUCKET,
            Key=key
        )
        pdf_bytes = response['Body'].read()
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        decrypt = cipher.decrypt(pdf_bytes)
        return decrypt



    @staticmethod
    def send_form(email: str, form_id: str, party_email: str, form_metadata: dict):
        track_key = f"{email}/forms/submissions/{form_id}/trackings.json"
        user_data_key = f"{email}/forms/submissions/{form_id}/form_user_data.json"

        try:
            # --- Load tracking.json ---
            try:
                resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=track_key)
                tracking_data = json.loads(resp['Body'].read().decode('utf-8'))
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    tracking_data = {}
                else:
                    raise

            party_data = tracking_data.get(party_email, {})
            status = party_data.get("status", {})

            if "sent" not in status:
                client_info = form_metadata.get("client_info")
                if client_info and hasattr(client_info, "dict"):
                    client_info = client_info.dict()

                status["sent"] = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "client_info": client_info or {}
                }

            form_metadata_copy = form_metadata.copy()

            form_metadata_copy["email_responses"] = [
                resp.dict() if hasattr(resp, "dict") else resp
                for resp in form_metadata_copy.get("email_responses", [])
            ]

            holder = form_metadata_copy.get("holder")
            if holder and hasattr(holder, "dict"):
                form_metadata_copy["holder"] = holder.dict()

            def serialize_parties(parties):
                return [p.dict() if hasattr(p, "dict") else p for p in parties]

            party_data.update({
                "form_id": form_id,
                "status": status,
                "validityDate": form_metadata_copy.get("validityDate"),
                "remainder": form_metadata_copy.get("remainder"),
                "party_id": form_metadata_copy.get("party_id"),
                "party_email": form_metadata_copy.get("party_email"),
                "party_name": form_metadata_copy.get("party_name"),
                "email_responses": form_metadata_copy.get("email_responses", []),
                "holder": form_metadata_copy.get("holder", {}),
                "created_at": form_metadata_copy.get("created_at"),
                "cc_emails": form_metadata_copy.get("cc_emails", [])
            })
            tracking_data[party_email] = party_data

            # --- Load form_user_data.json ---
            try:
                resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=user_data_key)
                form_user_data = json.loads(resp['Body'].read().decode('utf-8'))
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    form_user_data = {}
                else:
                    raise

            # Prepopulate with id/label if not already present
            existing_fields = form_user_data.get(party_email, [])
            if not existing_fields:
                form_metadata_copy.get("fields", [])

                form_user_data[party_email] = [
                    {
                        "id": f["id"] if isinstance(f, dict) else getattr(f, "id"),
                        "label": f["label"] if isinstance(f, dict) else getattr(f, "label"),
                        "type": f["type"] if isinstance(f, dict) else getattr(f, "type"),
                        "required": f.get("required", False) if isinstance(f, dict) else getattr(f, "required", False),
                        "sensitive": f.get("sensitive", False) if isinstance(f, dict) else getattr(f, "sensitive",False),
                        "disclaimerText": f.get("disclaimerText", None) if isinstance(f, dict) else getattr(f, "disclaimerText",None),
                        "value": "",
                    }
                    for f in form_metadata_copy.get("fields", [])
                ]

            # --- Save both files ---

            logger.info(existing_fields)
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=track_key,
                Body=json.dumps(tracking_data, indent=2).encode('utf-8'),
                ContentType='application/json'
            )

            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=user_data_key,
                Body=json.dumps(form_user_data, indent=2).encode('utf-8'),
                ContentType='application/json'
            )

            logger.info(f"Sent metadata updated for {party_email} in form {form_id}")

        except Exception as e:
            logger.error(f"Failed to update sent metadata for {party_email} in form {form_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update sent metadata")

    @staticmethod
    def cancel_form_party(email: str, data: FormCancelled, form_id: str, party_email: str, reason: str = None):
        """
        Mark a form party's tracking as cancelled.
        Updates trackings.json for the given form_id.
        """
        track_key = f"{email}/forms/submissions/{form_id}/trackings.json"
        now = datetime.utcnow().isoformat() + "Z"

        try:
            # --- Load tracking.json ---
            try:
                resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=track_key)
                tracking_data = json.loads(resp['Body'].read().decode('utf-8'))
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    raise HTTPException(status_code=404, detail="Form tracking not found")
                raise

            # Find party entry
            party_data = tracking_data.get(party_email)
            if not party_data:
                raise HTTPException(status_code=404, detail=f"No tracking found for party {party_email}")

            # --- Update status logs ---
            status = party_data.get("status", {})

            if "cancelled" not in status:
                status["cancelled"] = []

            status["cancelled"].append({
                "timestamp": now,
                "client_info": data.client_info,
                "holder": data.holder,
                "reason": reason or "Cancelled by system"
            })

            party_data["status"] = status
            party_data["last_updated"] = now
            tracking_data[party_email] = party_data

            # Save back
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=track_key,
                Body=json.dumps(tracking_data, indent=2).encode("utf-8"),
                ContentType="application/json"
            )

            logger.info(f"[cancel_form_party] Cancelled {party_email} in form {form_id}")
            return {"msg": f"Party {party_email} cancelled successfully", "form_id": form_id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel {party_email} in form {form_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to cancel party")

    @staticmethod
    def get_form_party_name(email: str, form_id: str, party_email: str) -> str:
        """
        Get the party's name from trackings.json for a given form_id and party_email.
        """
        track_key = f"{email}/forms/submissions/{form_id}/trackings.json"

        try:
            # Load tracking.json
            resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=track_key)
            tracking_data = json.loads(resp['Body'].read().decode('utf-8'))

            # Find party entry
            party_data = tracking_data.get(party_email)
            if not party_data:
                raise HTTPException(status_code=404, detail=f"No tracking found for party {party_email}")

            # Return name if exists
            return party_data.get("name", "")

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise HTTPException(status_code=404, detail="Form tracking not found")
            raise
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get name for {party_email} in form {form_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch party name")

    @staticmethod
    def get_form_track(email, form_id, party_email):
        s3_key = f"{email}/metadata/forms/{form_id}/tracking.json"
        resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=s3_key)
        return json.loads(resp['Body'].read().decode("utf-8"))

    @staticmethod
    def update_tracking_status_by_party(email: str, form_id: str, party_email: str, new_status: str,
                                        request: Request):
        s3_key = f"{email}/metadata/forms/{form_id}/tracking.json"
        try:
            resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=s3_key)
            tracking_data = json.loads(resp['Body'].read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to fetch tracking data from S3: {e}")
            raise HTTPException(status_code=404, detail="Form tracking metadata not found")

        updated = False
        current_time = datetime.now(timezone.utc).isoformat()

        client_ip = request.client.host if request.client else "Unknown"
        user_agent = request.headers.get("user-agent", "Unknown")
        device, browser, os = "Unknown Device", "Unknown Browser", "Unknown OS"
        location_info = {}

        try:
            ua = parse(user_agent)
            device = ua.device.family or "Unknown Device"
            browser = ua.browser.family or "Unknown Browser"
            os = ua.os.family or "Unknown OS"
        except Exception as e:
            logger.warning(f"user_agents parsing failed: {e}")

        try:
            ip_lookup_url = f"https://ipapi.co/{client_ip}/json/"
            response = requests.get(ip_lookup_url, timeout=5)
            if response.status_code == 200:
                location_info = response.json()
        except Exception as e:
            logger.warning(f"Geolocation lookup failed for IP={client_ip}: {e}")

        context = {
            "status": new_status,
            "dateTime": current_time,
            "details": {
                "ip": client_ip,
                "device": device,
                "browser": browser,
                "os": os,
                "location": {
                    "city": location_info.get("city"),
                    "region": location_info.get("region"),
                    "country": location_info.get("country_name"),
                    "latitude": location_info.get("latitude"),
                    "longitude": location_info.get("longitude"),
                    "postal": location_info.get("postal")
                },
                "user_agent": user_agent
            }
        }

        # tracking_data is a list; find matching party by id == party_email
        for party in tracking_data:
            if party.get("id") == party_email:
                if "status_history" not in party:
                    party["status_history"] = []
                party["status_history"].append(context)
                party["status"] = context
                updated = True
                break

        if not updated:
            raise HTTPException(status_code=404, detail="Party not found in tracking data")

        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(tracking_data).encode('utf-8'),
            ContentType="application/json"
        )

        logger.info(f"Tracking status updated: form_id={form_id}, party_email={party_email}, status={new_status}")
        return {"success": True, "updated_context": context}

    @staticmethod
    def update_party_status_by_tracking(email: str, form_id: str, party_email: str,
                                        new_status: str):
        s3_key = f"{email}/metadata/forms/{form_id}/tracking.json"
        logger.info(s3_key)
        resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=s3_key)
        tracking_data = json.loads(resp['Body'].read().decode("utf-8"))
        if not tracking_data:
            logger.info(f"{tracking_data} Tracking data is not found")
        updated = False
        for party in tracking_data:
            if party.get("id") == party_email:
                party["status"] = new_status
                updated = True
                break

        if not updated:
            raise HTTPException(status_code=404, detail="Party not found in the given tracking data")

        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(tracking_data).encode('utf-8'),
            ContentType="application/json"
        )

    @staticmethod
    def update_tracking_status_all_parties(email: str, form_id: str, new_status: str):
        prefix = f"{email}/metadata/forms/{form_id}/tracking.json"
        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        for obj in response.get("Contents", []):
            key = obj["Key"]
            resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
            tracking_data = json.loads(resp['Body'].read().decode("utf-8"))
            # Assuming tracking_data is a dict with status key or a list of parties:
            if isinstance(tracking_data, dict):
                tracking_data["status"] = new_status
            elif isinstance(tracking_data, list):
                for party in tracking_data:
                    party["status"] = new_status
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=key,
                Body=json.dumps(tracking_data).encode('utf-8'),
                ContentType="application/json"
            )

    @staticmethod
    async def resend_form_s3_tracking(email, form_id):
        prefix = f"{email}/metadata/forms/{form_id}/tracking.json"
        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        tracking_data = {}
        for obj in response.get("Contents", []):
            key = obj["Key"]
            party_email = key.split("/")[-1].replace(".json", "")
            data = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
            content = json.loads(data["Body"].read().decode("utf-8"))
            tracking_data[party_email] = content
        return tracking_data

    @staticmethod
    def get_all_tracking_id(email, form_id):
        prefix = f"{email}/metadata/forms/{form_id}/tracking.json"
        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        party_emails = [obj["Key"].split("/")[-1].replace(".json", "") for obj in response.get("Contents", [])]
        return party_emails

    @staticmethod
    def get_all_trackings(email, form_id):
        prefix = f"{email}/metadata/forms/{form_id}/tracking.json"
        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        tracking_data = {}
        for obj in response.get("Contents", []):
            key = obj["Key"]
            party_email = key.split("/")[-1].replace(".json", "")
            data = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
            content = json.loads(data["Body"].read().decode("utf-8"))
            tracking_data[party_email] = content
        return tracking_data
