from typing import List, Union
import re
from fastapi import Request, Depends
from auth_app.app.database.connection import db, get_document_send_count_for_user_this_month, \
    get_document_send_history_for_user
from auth_app.app.utils.auth_utils import JWTBearer
from auth_app.app.utils.subscription_plans import SUBSCRIPTION_PLANS
from repositories.s3_repo import get_folder_size
from utils.logger import logger
from jose import JWTError, ExpiredSignatureError

jwt_bearer = JWTBearer()



import traceback
import logging
from fastapi import Depends, HTTPException
from jose import JWTError, ExpiredSignatureError
from pymongo.errors import PyMongoError
from motor.motor_asyncio import AsyncIOMotorCollection


async def get_current_user(payload: dict = Depends(jwt_bearer)):
    try:
        # Extract email from token payload
        email = payload.get("user_email") or payload.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Missing email in token")

        # Get user from DB
        try:
            user = await db["users"].find_one({"email": email})
        except PyMongoError as db_err:
            logger.error(f"MongoDB error while fetching user: {db_err}", exc_info=True)
            raise HTTPException(status_code=500, detail="Database query failed")

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Format user object
        user["id"] = str(user["_id"])
        del user["_id"]

        # Add folder size info
        try:
            folder_size_bytes = get_folder_size(email)
        except Exception as fs_err:
            logger.error(f"Error calculating folder size for {email}: {fs_err}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Folder size calculation failed: {str(fs_err)}")

        folder_size_mb = round(folder_size_bytes / (1024 ** 2), 2)
        user["folder_size_bytes"] = folder_size_bytes
        user["folder_size_mb"] = folder_size_mb

        # Subscription info
        subscription_status = (
            payload.get("subscription_status")
            or user.get("subscription_status")
            or "free"
        )
        user["subscription_status"] = subscription_status

        # Calculate remaining e-sign sends
        plan = SUBSCRIPTION_PLANS.get(subscription_status.lower())
        if plan:
            monthly_limit = plan["limits"]["monthly_send_limit"]
            if monthly_limit is None:
                remaining_sends = None  # unlimited
            else:
                try:
                    sent_count = await get_document_send_count_for_user_this_month(email)
                except Exception as send_err:
                    logger.error(f"Error fetching send count for {email}: {send_err}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Failed to get document send count")

                remaining_sends = max(monthly_limit - sent_count, 0)
        else:
            monthly_limit = None
            remaining_sends = None

        user["monthly_limit"] = str(monthly_limit) if monthly_limit is not None else "unlimited"
        user["remaining_e_signs"] = str(remaining_sends) if remaining_sends is not None else "unlimited"

        # Roles from token
        token_roles = payload.get("role") or payload.get("roles")
        if token_roles:
            if isinstance(token_roles, str):
                token_roles = [token_roles]
            if "third-party" in token_roles:
                user["roles"] = ["third-party"]
                return user
            if "third-party-form" in token_roles:
                user["roles"] = ["third-party-form"]
                return user

        # Roles from DB
        db_roles = user.get("roles") or user.get("role")
        if isinstance(db_roles, str):
            db_roles = [db_roles]
        user["roles"] = db_roles or []

        # Add e-sign history
        try:
            e_sign_stats = await get_document_send_history_for_user(email)
            user.update(e_sign_stats)
        except Exception as hist_err:
            logger.error(f"Error fetching e-sign history for {email}: {hist_err}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch e-sign history")

        # Dark theme flag
        user["dark_theme"] = user.get("dark_theme") or False

        return user

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as jwt_error:
        raise HTTPException(status_code=401, detail=f"JWT decode error: {str(jwt_error)}")
    except HTTPException:
        raise  # Pass through existing HTTP errors
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")



def require_roles(allowed_roles: Union[str, List[str]]):
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    async def role_checker(user: dict = Depends(get_current_user)):
        if "role" not in user:
            raise HTTPException(status_code=403, detail="Missing role in user data")

        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Access denied: insufficient permissions.")

        return user  # You can return user or role info for further use

    return role_checker

from fastapi import Security, HTTPException

def get_email_from_token(
    payload: dict = Security(jwt_bearer)  # already a decoded JWT token
):
    print("Decoded JWT Payload:", payload)  # Simple print for full payload

    email: str = payload.get("domain_name")

    if email is None:
        email: str = payload.get("email")
        if email is None:
            raise HTTPException(status_code=400, detail="Email not found in token")
    return email

def get_role_from_token(
    payload: dict = Security(jwt_bearer)  # already a decoded JWT token
):
    print("Decoded JWT Payload:", payload)  # Simple print for full payload
    email: str = payload.get("role")
    if email is None:
        raise HTTPException(status_code=400, detail="Email not found in token")
    return email
def get_org_from_token(
    payload: dict = Security(jwt_bearer)  # already a decoded JWT token
):
    print("Decoded JWT Payload:", payload)  # Simple print for full payload
    org: str = payload.get("org")
    return org

def get_user_email_from_token(
    payload: dict = Security(jwt_bearer)  # already a decoded JWT token
):
    print("Decoded JWT Payload:", payload)  # Simple print for full payload
    email: str = payload.get("user_email")
    if email is None:
        raise HTTPException(status_code=400, detail="Email not found in token")
    return email



def path_pattern_to_regex(path_pattern: str) -> str:
    """
    Converts FastAPI-style path pattern to regex.
    Example: /users/{user_email} -> ^/users/[^/]+$
    """
    pattern = re.sub(r"{[^}]+}", r"[^/]+", path_pattern)
    return "^" + pattern + "$"

async def dynamic_permission_check(
    request: Request,
    user=Depends(get_current_user),
    org: str = Depends(get_org_from_token),
):
    method = request.method
    path = request.url.path

    # Normalize user roles → always a list
    user_roles = user.get("roles") or user.get("role")
    if isinstance(user_roles, str):
        user_roles = [user_roles]
    elif not isinstance(user_roles, list):
        user_roles = []

    logger.info(f"Resolved user roles: {user_roles}, org: {org or 'None'}")

    allowed = False

    # 1️⃣ Check org_roles if org is provided
    if org:
        org_doc = await db["org_roles"].find_one({"org_name": org})
        if org_doc and "roles" in org_doc:
            for role in org_doc["roles"]:
                if role["role_name"] in user_roles:
                    for perm in role.get("api_permissions", []):
                        if perm.get("method", "").upper() != method.upper():
                            continue
                        regex = path_pattern_to_regex(perm.get("url", ""))
                        if re.match(regex, path):
                            allowed = True
                            break
                if allowed:
                    break

    # 2️⃣ Fallback to default_roles if not allowed (or org is None)
    if not allowed:
        async for role_doc in db["default_roles"].find({"role_name": {"$in": user_roles}}):
            for perm in role_doc.get("api_permissions", []):
                if perm.get("method", "").upper() != method.upper():
                    continue
                regex = path_pattern_to_regex(perm.get("url", ""))
                if re.match(regex, path):
                    allowed = True
                    break
            if allowed:
                break

    if not allowed:
        raise HTTPException(status_code=403, detail="Access denied")
