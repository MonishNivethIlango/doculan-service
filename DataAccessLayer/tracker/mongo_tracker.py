
from motor.motor_asyncio import AsyncIOMotorClient
from .base import BaseTrackerStrategy
import logging

logger = logging.getLogger(__name__)

class MongoTracker(BaseTrackerStrategy):
    def __init__(self, db_url: str, db_name: str):
        self.client = AsyncIOMotorClient(db_url)
        self.db = self.client[db_name]
        self.collection = self.db["tracking"]

    async def add_status(self, file_key: str, user_email: str, status: str):
        await self.collection.insert_one({
            "file_key": file_key,
            "user_email": user_email,
            "status": status
        })



    async def update_status(self, file_key: str, user_email: str, status: str):
        logger.info(f"Updating status for file_key={file_key}, user_email={user_email}, new status={status}")

        result = await self.collection.update_one(
            {"file_key": file_key, "user_email": user_email},
            {"$set": {"status": status}}
        )

        if result.matched_count == 0:
            logger.warning(f"No matching document found for key={file_key} and user_email={user_email}")
        elif result.modified_count == 0:
            logger.info(f"Document matched but status was already '{status}' — nothing changed.")
        else:
            logger.info(f"Document status updated to '{status}' successfully.")

    async def get_status(self, file_key: str, user_email: str):
        return await self.collection.find_one(
            {"file_key": file_key, "user_email": user_email},
            {"_id": 0}
        )

    async def get_all_statuses(self):
        return await self.collection.find({}, {"_id": 0}).to_list(length=100)

    async def save_metadata(self, file_key: str, user_email: str, metadata: dict):
        await self.collection.update_one(
            {"file_key": file_key, "user_email": user_email},
            {"$set": {"metadata": metadata}},
            upsert=True
        )
