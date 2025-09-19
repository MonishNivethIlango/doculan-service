import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from apscheduler.triggers.date import DateTrigger

from app.schemas.tracking_schemas import DocumentRequest
from auth_app.app.database.connection import db
from auth_app.app.utils.security import scheduler
from utils.logger import logger

jobs_collection = db["scheduled_jobs"]


class SchedulerManager:
    @staticmethod
    async def init_scheduler():
        """
        Load all pending jobs from DB at startup and re-schedule them.
        If any are overdue, execute them immediately.
        """
        async for job in jobs_collection.find({"status": "pending"}):
            SchedulerManager._schedule_job(job)
        logger.info("✅ Scheduler started and pending jobs loaded.")

    import asyncio

    @staticmethod
    def _schedule_job(job: dict):
        """
        Schedule a job in APScheduler.
        If the schedule_time is in the past, execute immediately.
        """
        schedule_time = job["schedule_time"]

        # 🔹 Ensure schedule_time is timezone-aware (UTC)
        if schedule_time.tzinfo is None:
            schedule_time = schedule_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        loop = asyncio.get_event_loop()

        def run_async():
            asyncio.run_coroutine_threadsafe(SchedulerManager._execute_job(job), loop)

        if schedule_time <= now:
            # Run immediately if overdue
            logger.info(
                f"⚡ Job {job['job_id']} is overdue "
                f"(scheduled at {schedule_time}), running immediately."
            )
            run_async()
            return

        # Schedule for the future
        trigger = DateTrigger(run_date=schedule_time)
        aps_job = scheduler.add_job(
            run_async,
            trigger=trigger,
            id=job["job_id"],
            replace_existing=True,
            misfire_grace_time=None,
            coalesce=True,
        )

        logger.info(
            f"📌 Job scheduled: {job['job_id']} "
            f"(action={job['action']}, document={job['document_id']}, "
            f"tracking={job['tracking_id']}) → Next run at {aps_job.next_run_time}"
        )

    @staticmethod
    async def add_job(
        document_id: str,
        tracking_id: str,
        action: str,
        schedule_time: datetime,
        email: str,
        user_email: str,
        data: dict = None,
        max_retries: int = 3,
        retry_delay: int = 60,
    ):
        """
        Add a new job to DB and schedule it.
        """
        job = {
            "job_id": str(uuid4()),
            "document_id": document_id,
            "tracking_id": tracking_id,
            "email": email,
            "user_email": user_email,
            "action": action,
            "schedule_time": schedule_time,
            "status": "pending",
            "data": data or {},
            "retries": 0,
            "max_retries": max_retries,
            "retry_delay": retry_delay,  # seconds
        }
        await jobs_collection.insert_one(job)
        SchedulerManager._schedule_job(job)
        return job

    @staticmethod
    async def _execute_job(job: dict):
        """
        Execute a scheduled job safely with retry logic.
        """
        logger.info(f"▶️ Executing job {job['job_id']} at {datetime.now(timezone.utc).isoformat()}")

        db_job = await jobs_collection.find_one({"job_id": job["job_id"]})
        if not db_job:
            logger.warning(f"⚠️ Job {job['job_id']} not found in DB.")
            return
        if db_job["status"] != "pending":
            logger.info(f"⏭️ Skipping job {job['job_id']} (status={db_job['status']})")
            return

        try:
            if job["action"] == "reminder":
                await SchedulerManager._send_reminder(job)
            elif job["action"] == "send_email":
                await SchedulerManager._send_email(job)
            else:
                logger.warning(f"⚠️ Unknown action '{job['action']}' for job {job['job_id']}")

            await jobs_collection.update_one(
                {"job_id": job["job_id"]},
                {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}},
            )
            logger.info(f"✅ Job {job['job_id']} completed.")

        except Exception as e:
            retries = db_job.get("retries", 0)
            max_retries = db_job.get("max_retries", 3)
            retry_delay = db_job.get("retry_delay", 60)

            if retries < max_retries:
                new_time = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
                await jobs_collection.update_one(
                    {"job_id": job["job_id"]},
                    {
                        "$set": {
                            "status": "pending",
                            "error": str(e),
                            "schedule_time": new_time,
                        },
                        "$inc": {"retries": 1},
                    },
                )
                SchedulerManager._schedule_job({**job, "schedule_time": new_time})
                logger.warning(
                    f"🔄 Job {job['job_id']} failed ({e}), retry {retries + 1}/{max_retries}, "
                    f"rescheduled at {new_time}"
                )
            else:
                await jobs_collection.update_one(
                    {"job_id": job["job_id"]},
                    {
                        "$set": {
                            "status": "failed",
                            "error": str(e),
                            "failed_at": datetime.now(timezone.utc),
                        }
                    },
                )
                logger.error(
                    f"❌ Job {job['job_id']} permanently failed after {max_retries} retries: {e}"
                )

    @staticmethod
    async def _send_reminder(job: dict):
        from app.services.signature_service import SignatureHandler

        document_id, tracking_id, email, user_email = (
            job["document_id"],
            job["tracking_id"],
            job["email"],
            job["user_email"],
        )

        if document_id:
            await SignatureHandler.initiate_remainder(document_id, tracking_id, email, user_email)
            logger.info(f"[REMINDER] Sent for Document={document_id}, tracking={tracking_id}, email={email}")
        else:
            logger.warning(f"⚠️ Skipping reminder for {user_email}, missing document_id.")

    @staticmethod
    async def _send_email(job: dict):
        from app.services.signature_service import SignatureHandler

        try:
            document_data = job.get("data")
            if not document_data:
                logger.warning(f"Job {job['job_id']} missing document data, cannot send email.")
                return

            doc = DocumentRequest(**document_data)
            await SignatureHandler.initiate_singing_schedule(
                doc, job["tracking_id"], job["email"], job["user_email"]
            )
            logger.info(
                f"[EMAIL] Scheduled email sent for document {doc.document_id}, tracking={job['tracking_id']}"
            )

        except Exception as e:
            logger.error(
                f"Failed to send scheduled email for job {job['job_id']}: {e}", exc_info=True
            )


scheduler_manage = SchedulerManager()
