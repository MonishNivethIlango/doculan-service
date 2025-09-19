import json

from fastapi import HTTPException
from passlib.context import CryptContext
from jose import JWTError, jwt
from typing import Optional
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import timedelta
import pytz
from starlette import status

from app.services.email_service import email_service
from config import config
from database.db_config import s3_client
from utils.logger import logger

scheduler = AsyncIOScheduler()


# Environment & constants
SECRET_KEY = config.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
REFRESH_TOKEN_EXPIRE_DAYS = 2

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Password hashing utilities
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Access token creation with expiration
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=int(MINUTES)))
    to_encode.update({"exp": int(expire.timestamp())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    MINUTES = config.REFRESH_TOKEN_EXPIRE_MINUTES
    expire =  datetime.now(timezone.utc) + ( timedelta(minutes=int(MINUTES)))
    to_encode.update({"exp": expire, "scope": "refresh_token"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str, scope: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("scope") != scope:
            return None
        return payload
    except JWTError:
        return None

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

from datetime import datetime
from zoneinfo import ZoneInfo

def s3_get_json(bucket: str, key: str) -> dict:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to fetch S3 metadata: {e}")
        return {}


def is_party_signed(document_id: str, tracking_id: str, party_id: str, user_email: str) -> bool:
    metadata_path = f"{user_email}/metadata/tracking/{document_id}/{tracking_id}.json"
    metadata = s3_get_json(config.S3_BUCKET, metadata_path)
    for party in metadata.get("parties", []):
        if party.get("party_id") == party_id:
            return party.get("status", "").upper() == "SIGNED"
    return False
def is_tracking_active(document_id: str, tracking_id: str, user_email: str) -> bool:
    metadata_path = f"{user_email}/metadata/tracking/{document_id}/{tracking_id}.json"
    metadata = s3_get_json(config.S3_BUCKET, metadata_path)
    status_obj = metadata.get("tracking_status", {})
    tracking_status = status_obj.get("status", "").upper() if isinstance(status_obj, dict) else ""
    return tracking_status not in ["COMPLETED", "CANCELLED", "DECLINED", "EXPIRED"]


def parse_validity_date(validity_date_str: str, timezone: str) -> datetime:
    local_tz = ZoneInfo(timezone)
    local_dt = datetime.fromisoformat(validity_date_str).replace(tzinfo=local_tz)
    return local_dt.astimezone(pytz.UTC)

def schedule_reminder(sent_email: str, tracking_id: str, reminder_time: datetime):
    """
    Schedule reminder email job before expiry.
    """
    from app.services.email_service import EmailService  # Ensure import is valid
    scheduler.add_job(
        email_service.send_reminder_email,
        "date",
        run_date=reminder_time,
        args=[sent_email, tracking_id],
        id=f"reminder-{tracking_id}",
        replace_existing=True,
    )
async def create_signature_token(
    sent_email: str,
    tracking_id: str,
    party_id: str,
    email: str,
    document_id: str,
    validity_date_str: str,
    remainder_days: int,
    default_timezone: str = "UTC",
) -> dict:
    from utils.scheduler_manager import SchedulerManager, jobs_collection
    from auth_app.app.services.auth_service import AuthService

    try:
        # -------------------------
        # Handle "NOW" validity
        # -------------------------
        if validity_date_str.upper() == "NOW":
            tz = ZoneInfo(default_timezone)
            now_local = datetime.now(tz)
            validity_date = now_local + timedelta(minutes=6)  # temporary test token
            validity_date_str = validity_date.isoformat()
            logger.info("[TOKEN] [TEST MODE] Overriding validity_date_str to %s", validity_date_str)

        # Parse the validity date
        validity_date = parse_validity_date(validity_date_str, default_timezone)
        now_utc = datetime.now(pytz.UTC)

        # Ensure validity_date is in the future
        if validity_date <= now_utc:
            # Set to end of the same day in default timezone
            tz = ZoneInfo(default_timezone)
            validity_date = validity_date.replace(hour=23, minute=59, second=59, microsecond=0)
            if validity_date <= now_utc:
                raise ValueError(f"Validity date {validity_date.isoformat()} must be in the future.")

        # -------------------------
        # Fetch user/domain info
        # -------------------------
        exp_timestamp = int(validity_date.timestamp())
        domain = await AuthService.get_parent_email_and_domain(email)
        parent_email = domain.get("parent_email")
        domain_name = await AuthService.get_check_domain_by_user_email(email)

        # -------------------------
        # JWT Payload
        # -------------------------
        payload = {
            "tracking_id": tracking_id,
            "party_id": party_id,
            "user_email": email,
            "email": parent_email,
            "domain_name": domain_name,
            "document_id": document_id,
            "role": "third-party",
            "purpose": "sign_document",
            "exp": exp_timestamp,
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        logger.info("[TOKEN] Generated for %s (doc=%s, tracking=%s) exp=%s",
                    email, document_id, tracking_id, validity_date.isoformat())

        # -------------------------
        # Reminder scheduling
        # -------------------------
        reminder_time = None
        if remainder_days > 0:
            requested_reminder = validity_date - timedelta(days=remainder_days)
            if requested_reminder > now_utc:
                reminder_time = requested_reminder

        # Fallback reminders (only if remainder_days > 0)
        if remainder_days > 0 and not reminder_time:
            for offset in [720, 360, 180]:  # minutes
                fallback = validity_date - timedelta(minutes=offset)
                if fallback > now_utc:
                    reminder_time = fallback
                    break

        # Schedule reminder if determined
        if reminder_time:
            existing_job = await jobs_collection.find_one({
                "document_id": document_id,
                "tracking_id": tracking_id,
                "action": "reminder",
                "status": "completed"
            })
            if existing_job:
                logger.info("[TOKEN] Reminder job already exists (doc=%s, tracking=%s), skipping.",
                            document_id, tracking_id)
            else:
                try:
                    await SchedulerManager.add_job(
                        document_id=document_id,
                        tracking_id=tracking_id,
                        action="reminder",
                        schedule_time=reminder_time,
                        email=domain_name or parent_email,
                        user_email=email
                    )
                    logger.info("[TOKEN] Reminder scheduled for %s at %s UTC",
                                sent_email, reminder_time.isoformat())
                except Exception as e:
                    logger.error("[TOKEN] Failed to schedule reminder for doc=%s, tracking=%s: %s",
                                 document_id, tracking_id, str(e))

        return {"token": token, "validity_datetime": validity_date.isoformat()}

    except ValueError as ve:
        logger.warning("[TOKEN] Invalid validity_date for doc=%s, tracking=%s: %s",
                       document_id, tracking_id, str(ve))
        raise
    except Exception as e:
        logger.exception("[TOKEN] Unexpected error for doc=%s, tracking=%s: %s",
                         document_id, tracking_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to generate signature token.")


async def create_form_token(
    sent_email: str,               # Party email
    party_id: str,
    email: str,                    # Sender's email
    form_id: str,
    validity_date_str: str,
    remainder_days: int,
    default_timezone: str = "UTC",
) -> dict:
    from utils.scheduler_manager import SchedulerManager, jobs_collection
    from auth_app.app.services.auth_service import AuthService

    try:
        # -------------------------
        # Handle "NOW" validity
        # -------------------------
        if validity_date_str.upper() == "NOW":
            tz = ZoneInfo(default_timezone)
            now_local = datetime.now(tz)
            validity_date = now_local + timedelta(minutes=6)  # temporary test token
            validity_date_str = validity_date.isoformat()
            logger.info("[FORM] [TEST MODE] Overriding validity_date_str to %s", validity_date_str)

        # Parse the validity date (must return datetime)
        validity_date = parse_validity_date(validity_date_str, default_timezone)
        now_utc = datetime.now(pytz.UTC)

        # Ensure validity_date is in the future
        if validity_date <= now_utc:
            tz = ZoneInfo(default_timezone)
            validity_date = validity_date.replace(hour=23, minute=59, second=59, microsecond=0)
            if validity_date <= now_utc:
                raise ValueError(f"Validity date {validity_date.isoformat()} must be in the future.")

        # -------------------------
        # Fetch user/domain info
        # -------------------------
        exp_timestamp = int(validity_date.timestamp())
        domain = await AuthService.get_parent_email_and_domain(email)
        parent_email = domain.get("parent_email")
        domain_name = await AuthService.get_check_domain_by_user_email(email)

        # -------------------------
        # JWT Payload
        # -------------------------
        payload = {
            "form_id": form_id,
            "party_id": party_id,
            "user_email": email,
            "email": parent_email,
            "domain_name": domain_name,
            "role": "third-party-form",
            "purpose": "fill_form",
            "exp": exp_timestamp,
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        logger.info("[FORM] Token generated for %s (form=%s) exp=%s",
                    email, form_id, validity_date.isoformat())

        # -------------------------
        # Reminder scheduling
        # -------------------------
        reminder_time = None
        if remainder_days > 0:
            requested_reminder = validity_date - timedelta(days=remainder_days)
            if requested_reminder > now_utc:
                reminder_time = requested_reminder

        # Fallback reminders
        if remainder_days > 0 and not reminder_time:
            for offset in [720, 360, 180]:  # minutes
                fallback = validity_date - timedelta(minutes=offset)
                if fallback > now_utc:
                    reminder_time = fallback
                    break

        # Schedule reminder if found
        if reminder_time:
            existing_job = await jobs_collection.find_one({
                "form_id": form_id,
                "party_id": party_id,
                "action": "reminder",
                "status": "completed"
            })
            if existing_job:
                logger.info("[FORM] Reminder job already exists (form=%s, party=%s), skipping.",
                            form_id, party_id)
            else:
                try:
                    # await SchedulerManager.add_job(
                    #     form_id=form_id,
                    #     party_id=party_id,
                    #     action="reminder",
                    #     schedule_time=reminder_time,
                    #     email=domain_name or parent_email,
                    #     user_email=email
                    # )
                    pass
                    logger.info("[FORM] Reminder scheduled for %s at %s UTC",
                                sent_email, reminder_time.isoformat())
                except Exception as e:
                    logger.error("[FORM] Failed to schedule reminder for form=%s, party=%s: %s",
                                 form_id, party_id, str(e))

        return {"token": token, "validity_datetime": validity_date.isoformat()}

    except ValueError as ve:
        logger.warning("[FORM] Invalid validity_date for form=%s, party=%s: %s",
                       form_id, party_id, str(ve))
        raise
    except Exception as e:
        logger.exception("[FORM] Unexpected error for form=%s, party=%s: %s",
                         form_id, party_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to generate form token.")



from datetime import datetime, timezone
from dateutil.parser import parse as parse_datetime

def sanitize_datetime_string(dt_str: str) -> str:
    """
    Sanitize datetime string by removing redundant suffixes like `Z` after offset.
    """
    if dt_str.endswith("Z") and "+00:00" in dt_str:
        dt_str = dt_str.replace("+00:00Z", "+00:00")
    elif dt_str.endswith("Z"):
        dt_str = dt_str[:-1]
    return dt_str

def ensure_utc(dt: datetime) -> datetime:
    """
    Convert a datetime to UTC and make it timezone-aware if naive.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def calculate_new_validity_date(validity_date_str: str, original_sent_str: str) -> str:
    # Sanitize and parse
    original_sent_str = sanitize_datetime_string(original_sent_str)
    validity_date_str = sanitize_datetime_string(validity_date_str)

    original_sent = ensure_utc(parse_datetime(original_sent_str))
    original_validity = ensure_utc(parse_datetime(validity_date_str))

    # Duration calculation
    validity_duration = original_validity - original_sent

    # Compute new validity
    now = datetime.now(timezone.utc)
    new_validity = now + validity_duration

    return new_validity.isoformat()

