from bson import ObjectId, errors
from typing import Optional, List
from datetime import datetime

from auth_app.app.database.connection import db
from auth_app.app.schema.UserSchema import UserUpdate


class UserCRUD:
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[dict]:
        user = await db["users"].find_one({"email": email})
        if user:
            user["_id"] = str(user["_id"])
        return user

    @staticmethod
    async def get_all_users() -> List[dict]:
        cursor = db["users"].find()
        users = await cursor.to_list(length=100)

        for user in users:
            user["_id"] = str(user["_id"])

        return users

    @staticmethod
    async def update_user_by_email(email: str, user_data: UserUpdate) -> bool:
        data = {k: v for k, v in user_data.dict(exclude_unset=True).items()}
        data["updated_at"] = datetime.utcnow()

        result = await db["users"].update_one({"email": email}, {"$set": data})
        return result.modified_count > 0

    @staticmethod
    async def deactivate_user_by_email(email: str) -> bool:
        # Soft delete: set status to "inactive"
        result = await db["users"].update_one(
            {"email": email},
            {"$set": {"status": "inactive", "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    @staticmethod
    async def get_all_active_user_emails() -> List[str]:
        cursor = db["users"].find(
            {"status": {"$ne": "inactive"}},
            {"email": 1}
        )
        return [doc["email"] async for doc in cursor if "email" in doc]

    @staticmethod
    async def get_all_active_admin_emails() -> List[str]:
        cursor = db["users"].find(
            {"status": {"$ne": "inactive"}, "role": "admin"},
            {"email": 1, "master_id": 1, "parent_email": 1}
        )

        results = []
        async for doc in cursor:
            if "master_id" in doc and doc["master_id"]:
                # Extract domain name from email
                email = doc.get("email")
                if email and "@" in email:
                    domain = email.split("@", 1)[1]
                    results.append(domain)
            else:
                parent_email = doc.get("parent_email")
                if parent_email:
                    results.append(parent_email)

        return results
