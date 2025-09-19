import redis
import logging
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from redis import Sentinel
from datetime import datetime, timezone
import time

from app.api.routes import (
    files_api, form_api, signature, template_api,
    contacts_api, document_notification, ai_api, library_manager_api
)
from app.middleware.middlewareLogger import LoggerMiddleware
from app.services.signature_service import SignatureHandler
from auth_app.app.api.routes import auth_verify, columns, users, admin
from auth_app.app.database.connection import db
from auth_app.app.repository.user import UserCRUD
from auth_app.app.utils.default_roles import seed_admin_role_with_dynamic_routes, seed_roles
from auth_app.app.utils.security import scheduler
from config import config
from repositories.s3_repo import mark_expired_trackings
from utils.scheduler_manager import scheduler_manage

# Logger setup
logger = logging.getLogger("doculan")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def wrap_async_job(email: str):
    """
    Wraps the async mark_expired_trackings function in a synchronous APScheduler job.
    Logs execution time and errors clearly.
    """
    def wrapper():
        start_time = time.time()
        logger.info(f"▶️ Expiry job started for {email} at {datetime.now(timezone.utc).isoformat()}")
        try:
            expired_count = asyncio.run(mark_expired_trackings(email))
            duration = round(time.time() - start_time, 2)
            logger.info(f"✅ {email}: {expired_count} tracking(s) marked as expired in {duration}s.")
        except Exception as e:
            logger.error(f"❌ {email}: Failed to mark expired trackings - {e}", exc_info=True)
    return wrapper


def log_next_run(job):
    """Log the next run time for a job in APScheduler 4.x (tz-aware)."""
    try:
        job_from_scheduler = scheduler.get_job(job.id)
        if job_from_scheduler:
            next_run = job_from_scheduler.trigger.get_next_fire_time(None, datetime.now(timezone.utc))
            logger.info(f"📌 Job scheduled - {job.id} → Next run at {next_run}")
        else:
            logger.warning(f"⚠️ Could not fetch next run time for job {job.id}")
    except Exception as e:
        logger.error(f"❌ Failed to fetch next run time for job {job.id}: {e}", exc_info=True)


async def wait_for_services(max_retries: int = 30, delay: float = 2.0):
    """
    Wait until Redis Sentinel and MongoDB are ready.
    In dev mode: only MongoDB is checked (Redis master check skipped).
    """
    retries = 0
    redis_ok = config.ENV == "dev"  # ✅ skip redis check in dev
    mongo_ok = False

    while retries < max_retries:
        if not redis_ok:
            try:
                sentinel = Sentinel(
                    [(config.SENTINEL_DNS, config.SENTINEL_PORT)],
                    socket_timeout=0.5
                )
                redis_master = sentinel.master_for(
                    service_name=config.SENTINEL_SERVICE_NAME,
                    socket_timeout=0.5,
                    decode_responses=True
                )
                if redis_master.ping():
                    redis_ok = True
                    logger.info(f"✅ Redis master '{config.SENTINEL_SERVICE_NAME}' is reachable.")
            except Exception as e:
                logger.warning(f"⏳ Waiting for Redis... {e}")

        if not mongo_ok:
            try:
                await db.command("ping")
                mongo_ok = True
                logger.info(f"✅ MongoDB connected successfully: {config.MONGO_URI}")
            except Exception as e:
                logger.warning(f"⏳ Waiting for MongoDB... {e}")

        if redis_ok and mongo_ok:
            return True

        retries += 1
        await asyncio.sleep(delay)

    raise RuntimeError("❌ Redis or MongoDB did not become ready after retries")



@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ Block until Redis + MongoDB are ready
    await wait_for_services()

    # ✅ Start scheduler after services are ready
    scheduler.start()

    # Add init scheduler job
    try:
        job = scheduler.add_job(
            scheduler_manage.init_scheduler,   # pass callable, not awaited
            trigger="interval",
            minutes=1,
            id="[Remainder] - scheduler",
            replace_existing=True
        )
        log_next_run(job)
        logger.info(f"📆 Scheduler started with {len(scheduler.get_jobs())} jobs.")
    except Exception as e:
        logger.error(f"❌ Failed to add init_scheduler job: {e}", exc_info=True)

    # ✅ Schedule tracking expiry jobs
    try:
        active_emails = await UserCRUD.get_all_active_admin_emails()
        for email in active_emails:
            job = scheduler.add_job(
                wrap_async_job(email),
                trigger="interval",
                minutes=30,
                id=f"expire-trackings-{email}",
                replace_existing=True
            )
            log_next_run(job)

        logger.info(f"✅ Scheduled expiry jobs for {len(active_emails)} active users.")

    except Exception as e:
        logger.error(f"❌ Failed to schedule expiry jobs: {e}", exc_info=True)

    # ✅ Dynamic route collection for RBAC
    try:
        routes_info = []
        for route in app.routes:
            if isinstance(route, APIRoute):
                for method in route.methods:
                    if method != "HEAD":
                        routes_info.append({
                            "method": method,
                            "path": route.path,
                            "name": route.name,
                            "tags": route.tags or []
                        })

        await db.routes.delete_many({})
        if routes_info:
            await db.routes.insert_many(routes_info)

        await seed_admin_role_with_dynamic_routes(db, app)
        await seed_roles(db)
        logger.info("✅ Dynamic routes and roles seeded successfully.")

    except Exception as e:
        logger.error(f"❌ Failed during route/role seeding: {e}", exc_info=True)

    yield

    # 🛑 Shutdown scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler shutdown complete.")


def init_application() -> FastAPI:
    app = FastAPI(
        title="Doculan",
        description="Form Management",
        lifespan=lifespan
    )

    # Routers
    app.include_router(auth_verify.router, tags=["Auth"])
    app.include_router(admin.admin_router, tags=["Admin"])
    app.include_router(columns.router, tags=["Columns"])
    app.include_router(users.router, tags=["Users"])
    app.include_router(ai_api.router, tags=["AI Management"])
    app.include_router(library_manager_api.router, tags=["Library Management"])
    app.include_router(form_api.router, tags=["Form Manage"])
    app.include_router(template_api.router, tags=["Document Template"])
    app.include_router(signature.router, tags=["Document Tracker"])
    app.include_router(document_notification.router, tags=["Document Notification"])
    app.include_router(files_api.router, tags=["Files Operation"])
    app.include_router(contacts_api.router, tags=["Contact Manage"])

    # Middleware
    app.add_middleware(LoggerMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = init_application()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
