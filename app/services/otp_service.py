import json
from datetime import datetime, timedelta

from botocore.exceptions import ClientError
from fastapi import status, HTTPException, Request, Depends
from app.schemas.form_schema import OtpFormVerification
from app.schemas.tracking_schemas import OTPVerification
from app.services.audit_service import  document_tracking_manager
from app.services.email_service import email_service
from app.services.metadata_service import MetadataService
from config import config
from database.db_config import s3_client
from database.redis_db import generate_form_otp, verify_form_otp, generate_otp, verify_otp
from auth_app.app.api.routes.deps import get_email_from_token
from starlette import status

from central_logger import CentralLogger
logger = CentralLogger.get_logger()


class OtpService:
    @staticmethod
    def send_otp_party(email: str, party_id: str, tracking_id: str, document_id: str) -> dict:
        try:
            otp = generate_otp(party_id, tracking_id)
            email_data = MetadataService.get_email_by_party_id(email, tracking_id, document_id, party_id)
            recipient_email = email_data["email"]
            email_service.send_otp_verification_link(recipient_email=recipient_email, otp=otp)

            return {"message": "OTP sent successfully"}

        except HTTPException as http_exc:
            logger.error(f"Failed to send OTP: {http_exc.status_code}: {http_exc.detail}")
            raise http_exc  # 🔁 Re-raise to preserve correct status code
        except Exception as e:
            logger.exception("Unexpected error during OTP send")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP due to internal server error"
            )

    @staticmethod
    async def verify_otp_for_party(email: str, data: OTPVerification) -> dict:
        try:
            if verify_otp(data.party_id, data.tracking_id, data.otp):
                await document_tracking_manager.log_action(email, data.document_id, data.tracking_id, "OTP_VERIFIED",
                                                   data.client_info, data.party_id)
                return {"status": "opened","detail":"OTP_VERIFIED"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="A new OTP has been sent. Kindly check your inbox."
                )

        except Exception as e:
            logger.error(f"OTP verification error: {e}")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OTP"
            )

    @staticmethod
    def send_form_otp(form_id: str, party_email: str, email: str = Depends(get_email_from_token)):
        try:
            logger.info(f"Sending OTP for form_id: {form_id}, party_email: {party_email}, requested_by: {email}")

            # Read trackings.json from S3
            key = f"{email}/forms/submissions/{form_id}/trackings.json"
            try:
                resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
                tracking_data = json.loads(resp['Body'].read().decode('utf-8'))
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    raise HTTPException(status_code=404, detail="Tracking data not found for this form")
                else:
                    raise

            # Validate party_email exists in tracking data
            if party_email not in tracking_data:
                raise HTTPException(status_code=404, detail="Party email not found in this form tracking")

            # Generate OTP if the party exists
            otp = generate_form_otp(form_id, party_email)
            email_service.send_otp_verification_link(party_email, otp)

            return {
                "message": "OTP sent successfully",
                "party_email": party_email,
                "form_id": form_id
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending OTP for form_id {form_id}, party_email {party_email}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error while sending OTP")
        except Exception as e:

            logger.exception("Unexpected error during OTP send")

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to send OTP due to internal server error"
            )

    @staticmethod
    def generate_otp(length: int = 6) -> str:
        from random import randint
        return str(randint(10 ** (length - 1), 10 ** length - 1))

    @staticmethod
    def verify_form_otp_for_party(email: str, data: OtpFormVerification, request: Request = None) -> dict:
        from starlette import status
        try:
            is_valid = verify_form_otp(data.form_id, data.party_email, data.otp)

            if not is_valid:
                raise HTTPException(status_code=400, detail="Invalid OTP")

            logger.info(f"OTP verified for form_id: {data.form_id}, party_email: {data.party_email}")

            # Update 'opened' status timestamp in S3 tracking JSON
            key = f"{email}/forms/submissions/{data.form_id}/trackings.json"
            try:
                resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
                content = resp['Body'].read().decode('utf-8')
                data_json = json.loads(content)
            except s3_client.exceptions.NoSuchKey:
                data_json = {}
            except Exception as e:
                logger.error(f"Failed to read tracking JSON for updating opened status: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to update opened status")

            party_data = data_json.get(data.party_email, {})

            # --- Maintain 'opened_logs' as a list ---
            opened_logs = party_data.get("opened_logs", [])

            client_info_dict = data.client_info.dict() if data.client_info else {}
            opened_logs.append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "client_info": client_info_dict
            })

            party_data["opened_logs"] = opened_logs
            data_json[data.party_email] = party_data

            # Save back to S3
            try:
                s3_client.put_object(
                    Bucket=config.S3_BUCKET,
                    Key=key,
                    Body=json.dumps(data_json, indent=2).encode('utf-8'),
                    ContentType='application/json'
                )
                logger.info(f"'opened' status updated for party_email: {data.party_email}")
            except Exception as e:
                logger.error(f"Failed to update tracking JSON in S3: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to update opened status")

            return {
                "party_email": data.party_email,
                "form_id": data.form_id,
                "status": "OTP Verified and opened status logged",
                "opened_logs": party_data["opened_logs"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying OTP for form_id {data.form_id}, party_email {data.party_email}: {str(e)}")

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A new OTP has been sent. Kindly check your inbox."
            )
