# app/services/auth_service.py
import asyncio
import logging
from typing import Union, Optional, Dict
from zoneinfo import available_timezones

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import PyMongoError
from starlette import status
from auth_app.app.database.connection import db
from auth_app.app.exceptions.custom_exceptions_user import DatabaseError, DomainMismatchError, UserAlreadyExistsError, \
    RegistrationError, DomainAlreadyRegisteredError
from auth_app.app.schema.AuthSchema import PreferencesOut
from auth_app.app.schema.UserSchema import UserCreate, UserCreateAdmin, AdminUserCreate
from auth_app.app.services.stripe_service import StripeService
from auth_app.app.utils import security
from auth_app.app.utils.security import create_refresh_token
import requests

logger = logging.getLogger("user_registration")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Fetch free/public email domains (cache in memory)
try:
    url = "https://raw.githubusercontent.com/kikobeats/free-email-domains/master/domains.json"
    response = requests.get(url)
    response.raise_for_status()
    FREE_EMAIL_DOMAINS = set(response.json())
except Exception as e:
    logger.error(f"Failed to load public email domains: {e}")
    FREE_EMAIL_DOMAINS = set()

def is_restricted(email: str) -> bool:
    domain = email.split('@')[-1].lower()
    return domain in FREE_EMAIL_DOMAINS
class AuthService:

    @staticmethod
    async def register_user(
            user_data: Union[UserCreate, UserCreateAdmin, AdminUserCreate],
            created_by_admin: bool = False
    ) -> str:
        users = db["users"]
        master_col = db["master"]

        try:
            # ✅ Check for existing user
            existing_user = await users.find_one({"email": user_data.email})
            if existing_user:
                logger.warning(f"Attempt to register existing email: {user_data.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email '{user_data.email}' is already registered"
                )

            user_dict = user_data.dict()
            email_domain = user_dict["email"].split("@")[1].lower()
            logger.info(f"Registering user '{user_dict['email']}' with domain '{email_domain}'")

            # 🔹 Case 1: Restricted/public domain → no master
            if is_restricted(user_dict["email"]):
                logger.info(f"Restricted domain detected ({email_domain}), skipping master creation")
                user_dict["master_id"] = None
                user_dict["parent_email"] = f"{email_domain}/{user_dict['email']}"
                is_created_by_admin = False

            # 🔹 Case 2: Organizational domain
            else:
                existing_master = await master_col.find_one({"domain_name": email_domain})
                if existing_master:
                    # Domain exists → only admin can add user
                    if not created_by_admin:
                        logger.warning(f"Self-registration blocked for domain '{email_domain}'")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Domain '{email_domain}' is already registered. Only admin can add users."
                        )

                    # Admin adding a user
                    master_id = str(existing_master["_id"])
                    user_dict["master_id"] = master_id
                    user_dict["parent_email"] = existing_master["parent_email"]
                    is_created_by_admin = True
                    logger.info(f"Admin adding user under existing master ID: {master_id}")

                else:
                    # First org user → create master (becomes admin)
                    master_doc = {"domain_name": email_domain, "parent_email": user_dict["email"]}
                    try:
                        master_result = await master_col.insert_one(master_doc)
                    except PyMongoError as e:
                        logger.error(f"Failed to create master for domain '{email_domain}': {e}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create organization master"
                        ) from e

                    master_id = str(master_result.inserted_id)
                    user_dict["master_id"] = master_id
                    user_dict["parent_email"] = user_dict["email"]
                    is_created_by_admin = False
                    logger.info(f"Created new master for domain '{email_domain}' with ID {master_id}")

                    # ✅ Set encryption only for first org user (master creation)
                    try:
                        encryption_email = f"doculan@{email_domain}"
                        await db["encryption"].update_one(
                            {"domain": email_domain},
                            {"$set": {"encryption_email": encryption_email}},
                            upsert=True
                        )
                        logger.info(f"Set encryption email for new master: {encryption_email}")
                    except PyMongoError as e:
                        logger.error(f"Failed encryption update for domain '{email_domain}': {e}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to update encryption"
                        ) from e

            # ✅ Set temporary password for admin-added users
            if is_created_by_admin:
                user_dict["is_temp_password"] = True

            # ✅ Hash password
            try:
                hashed_password = security.hash_password(user_dict["password"])
            except Exception as e:
                logger.error(f"Password hashing failed for '{user_dict['email']}': {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Password hashing failed"
                ) from e

            user_dict["hashed_password"] = hashed_password
            user_dict.pop("password", None)
            user_dict["extra"] = user_dict.get("extra", {})

            # ✅ Insert user
            try:
                result = await users.insert_one(user_dict)
            except PyMongoError as e:
                logger.error(f"Failed to insert user '{user_dict['email']}': {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to register user"
                ) from e

            logger.info(f"User '{user_dict['email']}' registered successfully with ID {result.inserted_id}")

            # ✅ Update parent-child mapping only for admin-added org users
            if not is_restricted(user_dict["email"]) and is_created_by_admin:
                try:
                    await db["parent_child"].update_one(
                        {"parent_email": user_dict["parent_email"]},
                        {"$addToSet": {"child_users": user_dict["email"]}},
                        upsert=True
                    )
                    logger.info(f"Updated parent-child for '{user_dict['email']}'")
                except PyMongoError as e:
                    logger.error(f"Failed parent-child update for '{user_dict['email']}': {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update parent-child"
                    ) from e

            return str(result.inserted_id)

        except HTTPException:
            raise  # propagate already-raised HTTPExceptions
        except Exception as e:
            logger.exception(f"Unexpected error during user registration: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during registration"
            ) from e

    @staticmethod
    async def get_domain_by_user_email(user_email: str):
        users_col = db["users"]
        master_col = db["master"]

        # Find the user first
        user = await users_col.find_one({"email": user_email})
        if not user:
            raise ValueError("User not found")

        master_id = user.get("master_id")
        if master_id:
            logger.info(master_id)
            # Get domain_name from master collection
            master_id = ObjectId(master_id)
            master_doc = await master_col.find_one({"_id": master_id})
            if not master_doc:
                raise ValueError("Master document not found")

            domain_name = master_doc.get("domain_name")
        else:
            domain_name = user.get("parent_email")

        return domain_name

    @staticmethod
    async def get_check_domain_by_user_email(user_email: str):
        users_col = db["users"]
        master_col = db["master"]

        # Find the user first
        user = await users_col.find_one({"email": user_email})
        if not user:
            raise ValueError("User not found")

        master_id = user.get("master_id")
        if master_id:
            logger.info(master_id)
            # Get domain_name from master collection
            master_id = ObjectId(master_id)
            master_doc = await master_col.find_one({"_id": master_id})
            if not master_doc:
                raise ValueError("Master document not found")

            domain_name = master_doc.get("domain_name")
        else:
            domain_name = None

        return domain_name

    @staticmethod
    def get_user_name_by_email(email: str) -> Optional[str]:
        users = db["users"]
        user = users.find_one({"email": email}, {"name": 1})
        return user["name"] if user and "name" in user else None

    @staticmethod
    async def authenticate_user(email: str, password: str):
        users = db["users"]
        user = await users.find_one({"email": email})

        if not user or not security.verify_password(password, user.get("hashed_password", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        if user.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not active."
            )

        return user

    @staticmethod
    async def create_token(user: dict):
        user_email = user["email"]
        user_id = str(user["_id"])
        role = user.get("role", "user")
        name = user.get("name", "")

        parent_email = user_email
        subscription_status = user.get("subscription_status", "0")

        if role == "admin":
            loop = asyncio.get_event_loop()
            subscription_status = await loop.run_in_executor(
                None,
                lambda: StripeService.check_subscription_by_email(parent_email, subscription_status)
            )

            # Persist updated subscription_status in DB
            await db["users"].update_one(
                {"_id": user["_id"]},
                {"$set": {"subscription_status": subscription_status}}
            )

        else:
            mapping = await db["parent_child"].find_one({"child_users": user_email})
            if not mapping:
                raise ValueError("User is not linked to any admin")
            parent_email = mapping["parent_email"]

            loop = asyncio.get_event_loop()
            subscription_status = await loop.run_in_executor(
                None,
                lambda: StripeService.check_subscription_by_email(parent_email, subscription_status)
            )

            # Persist updated subscription_status in DB
            await db["users"].update_one(
                {"_id": user["_id"]},
                {"$set": {"subscription_status": subscription_status}}
            )
        domain_name = await auth_service.get_domain_by_user_email(user_email)
        org  = await auth_service.get_check_domain_by_user_email(user_email)
        token_data = {
            "sub":user_email,
            "id": user_id,
            "role": role,
            "name": name,
            "user_email": user_email,
            "email": parent_email,
            "domain_name":domain_name,
            "subscription_status": subscription_status,
            "org":org
        }

        return (
            security.create_access_token(token_data),
            subscription_status,
            create_refresh_token(token_data)
        )
    @staticmethod

    async def get_parent_email_and_domain(email: str) -> Dict[str, Optional[str]]:
        try:
            users = db["users"]

            # Fetch user by email
            user = await users.find_one({"email": email})
            if not user:
                return {"email": None, "domain_name": None}

            parent_email = user.get("parent_email")

            return {
                "parent_email": parent_email if parent_email else None,
            }

        except Exception as e:
            logger.error(f"Error in get_parent_email_and_domain for {email}: {e}")
            return {"email": None, "domain_name": None}

    @staticmethod
    def validate_timezone(timezone: str) -> bool:
        return timezone in available_timezones()

    @staticmethod
    async def update_user_preferences(user_id: str, preferences: dict):
        users = db["users"]
        update_result = await users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"preferences": preferences}}
        )
        return update_result.modified_count > 0

    @staticmethod
    async def get_preferences_by_email(email: str) -> PreferencesOut:
        user = await db["users"].find_one({"email": email}, {"preferences": 1})
        if not user or "preferences" not in user:
            return PreferencesOut()

        prefs = user["preferences"]
        return PreferencesOut(
            dateFormat=prefs.get("dateFormat"),
            timeFormat=prefs.get("timeFormat"),
            timezone=prefs.get("timezone"),
        )

    @staticmethod
    async def get_logo_and_theme(email: str) -> Optional[Dict[str, str]]:
        users = db["users"]
        user = await users.find_one(
            {"email": email},
            {"_id": 0, "logo": 1, "theme": 1, "organization": 1, "extra": 1}
        )

        if not user:
            return None

        # Priority: top-level > inside 'extra'
        logo = user.get("logo") or user.get("extra", {}).get("logo")
        theme = user.get("theme") or user.get("extra", {}).get("theme")
        organization = user.get("organization") or user.get("extra", {}).get("organization")

        return {
            "logo": logo or "images/virtualan_logo.png",
            "theme": theme or "#001f3f",
            "organization": organization or "Doculan"
        }

    @staticmethod
    async def get_domain_if_master(email: str) -> Union[str, bool]:
        """
        Given a user email:
          - Look up the user in `users`.
          - If a master_id exists, fetch the master record from `master` collection.
          - Return the master domain_name if present.
          - Return False if no user, no master_id, or no domain_name.
        """
        users = db["users"]
        masters = db["master"]

        # Lookup user by email
        user = await users.find_one({"email": email}, {"master_id": 1})
        if not user:
            return email  # user not found

        master_id = user.get("master_id")
        if not master_id:
            return email  # user has no master

        # Ensure master_id is ObjectId (in case it's stored as string)
        if isinstance(master_id, str):
            try:
                master_id = ObjectId(master_id)
            except Exception:
                return email

        # Fetch master record
        master_doc = await masters.find_one({"_id": master_id}, {"domain_name": 1})
        if not master_doc or "domain_name" not in master_doc:
            return email

        return master_doc["domain_name"]

auth_service = AuthService()