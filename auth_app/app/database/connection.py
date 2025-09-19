from datetime import datetime

from pymongo import MongoClient  # <-- use pymongo for APScheduler
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

# Your existing imports
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from dotenv import load_dotenv

from auth_app.app.utils.subscription_plans import SUBSCRIPTION_PLANS
from auth_app.settings import settings
from typing import Any, Mapping

load_dotenv()

# Async client for your app's async operations
MONGO_URI = settings.MONGO_URI
DB_NAME = settings.DB_NAME
async_client = AsyncIOMotorClient(MONGO_URI)
db = async_client[DB_NAME]
tracker_collection = async_client[settings.DB_NAME]["signature_tracker"]
kms_collection = async_client[settings.DB_NAME]["kms_keys"]
# mongo_sync_client = MongoClient(MONGO_URI)  # For APScheduler's MongoDBJobStore
usage_collection = db["document_usage"]
esignature_collection = db["esignature"]

async def get_document_send_count_for_user_this_month(email: str) -> int:
    now = datetime.utcnow()
    record = await usage_collection.find_one({
        "email": email,
        "year": now.year,
        "month": now.month
    })
    return record["send_count"] if record else 0


async def increment_send_counter_for_user(email: str, year: int, month: int):
    await usage_collection.update_one(
        {"email": email, "year": year, "month": month},
        {"$inc": {"send_count": 1}},
        upsert=True
    )
from datetime import datetime

async def get_remaining_document_sends(email: str, plan_name: str) -> int | None:
    """
    Returns the number of remaining document sends for the user this month.
    If the plan has unlimited sends, returns None.
    """
    plan = SUBSCRIPTION_PLANS.get(plan_name.lower())
    if not plan:
        raise ValueError(f"Unknown subscription plan: {plan_name}")

    monthly_limit = plan["limits"]["monthly_send_limit"]

    # Unlimited plan
    if monthly_limit is None:
        return None

    # Count how many documents the user has sent this month
    sent_count = await get_document_send_count_for_user_this_month(email)

    # Remaining sends (minimum zero)
    remaining = max(monthly_limit - sent_count, 0)
    return remaining

import calendar
from datetime import datetime

async def get_document_send_history_for_user(email: str):
    now = datetime.utcnow()
    cursor = usage_collection.find({"email": email}).sort([("year", -1), ("month", -1)])
    records = await cursor.to_list(length=None)

    history = []
    total_send_count = 0
    current_month_count = 0

    for record in records:
        send_count = record.get("send_count", 0)
        total_send_count += send_count
        is_current_month = (record["year"] == now.year and record["month"] == now.month)
        if is_current_month:
            current_month_count = send_count

        history.append({
            "year": record["year"],
            "month": record["month"],
            "month_name": calendar.month_name[record["month"]],
            "send_count": send_count,
            "is_current_month": is_current_month
        })

    return {
        "total_send_count": str(total_send_count),
        "current_month_count": str(current_month_count),
        "history": history
    }


def get_user_collection() -> AsyncIOMotorCollection[Mapping[str, Any] | Any]:
    return db.get_collection("users")

def get_signature_tracker_collection() -> AsyncIOMotorCollection[Mapping[str, Any] | Any]:
    return db.get_collection("signature_tracker")
# Sync client for APScheduler
sync_client = MongoClient(MONGO_URI)  # ✅ This is the fix

jobstores = {
    'default': MongoDBJobStore(database='scheduler_db', collection='jobs', client=sync_client)
}

# scheduler = BackgroundScheduler(jobstores=jobstores)
# scheduler.start()
def save_document_url(tracking_id: str, document_url: str):
    collection = get_signature_tracker_collection()
    collection.update_one(
        {"tracking_id": tracking_id},
        {"$set": {"document_url": document_url, "url_created_at": datetime.utcnow()}},
        upsert=True
    )
