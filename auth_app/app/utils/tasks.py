# tasks.py
import asyncio
from app.services.email_service import EmailService
from repositories.s3_repo import mark_expired_trackings


def reminder_job(tracking_id: str):
    """
    Wrapper for async email job to be run by APScheduler.
    """
    service = EmailService()
    asyncio.run(service.send_reminder_email_to_pending_parties(tracking_id))


async def async_expiry_job(email: str):
    await mark_expired_trackings(email)  # ✅ mark_expired_trackings must be async


def expiry_job(email: str):
    try:
        asyncio.run(async_expiry_job(email))
    except Exception as e:
        print(f"[ERROR] Expiry job failed: {e}")
