import secrets
from typing import List

import requests
from fastapi import APIRouter, HTTPException, Depends, Body, Response, Request
from pydantic import EmailStr, BaseModel
from pymongo.errors import PyMongoError
from starlette import status
from user_agents import parse

from app.services.email_service import EmailService, email_service
from auth_app.app.api.routes.deps import get_current_user
from auth_app.app.database.connection import db
from auth_app.app.schema.AuthSchema import TokenResponse, UserLogin, PreferencesUpdate
from auth_app.app.schema.UserSchema import UserCreate, UserCreateAdmin, AdminUserCreate
from auth_app.app.services.auth_service import AuthService
from auth_app.app.utils.auth_utils import JWTBearer
from auth_app.app.utils import security
from auth_app.app.utils.security import verify_token, create_access_token
from config import config
from utils.logger import logger

router = APIRouter(prefix="/auth", tags=["Auth"])
jwt_bearer = JWTBearer()

@router.get("/protected", dependencies=[Depends(jwt_bearer)])
async def protected_route():
    return {"message": "You are authenticated!"}



@router.get("/ipinfo", dependencies=[Depends(jwt_bearer)])
def get_ipinfo(request: Request, ip: str = None):
    try:
        # Detect IP
        if not ip:
            x_forwarded_for = request.headers.get("x-forwarded-for")
            if x_forwarded_for:
                ip = x_forwarded_for.split(",")[0].strip()
            else:
                ip = request.client.host

        # Query IP info
        response = requests.get(f"{config.IP_CONFIG_URL}", timeout=5)
        response.raise_for_status()
        ip_data = response.json()

        # Parse User-Agent
        user_agent_str = request.headers.get("user-agent", "")
        user_agent = parse(user_agent_str)

        # Device type mapping
        if user_agent.is_mobile:
            device_type = "Mobile"
        elif user_agent.is_tablet:
            device_type = "Tablet"
        elif user_agent.is_pc:
            device_type = "PC/Laptop"
        else:
            device_type = "Unknown"

        device_info = {
            "device_type": device_type,
            "os": user_agent.os.family,
            "os_version": user_agent.os.version_string,
            "browser": user_agent.browser.family,
            "browser_version": user_agent.browser.version_string,
        }

        return {
            "ip_info": ip_data,
            "device_info": device_info,
            "user_agent": user_agent_str
        }

    except Exception as e:
        return {"error": str(e)}

class UserDomainReassignRequest(BaseModel):
    user_email: str
    new_domain: str
    encryption_email: str | None = None   # optional, auto-generate if not given


@router.put("/users/reassign-domain")
async def reassign_user_domain(request: UserDomainReassignRequest):
    users = db["users"]
    master_col = db["master"]
    encryption_col = db["encryption"]

    user_email = request.user_email.lower()
    new_domain = request.new_domain.lower()

    try:
        # ✅ Step 1: Find the user
        user = await users.find_one({"email": user_email})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_email}' not found"
            )

        # ✅ Step 2: Find or create master
        master = await master_col.find_one({"domain_name": new_domain})
        if not master:
            master_doc = {
                "domain_name": new_domain,
                "parent_email": user_email   # first user becomes parent/admin
            }
            master_result = await master_col.insert_one(master_doc)
            master_id = str(master_result.inserted_id)
            parent_email = user_email
            created_new_master = True
        else:
            master_id = str(master["_id"])
            parent_email = master["parent_email"]
            created_new_master = False

        # ✅ Step 3: Update user with master_id + parent_email
        await users.update_one(
            {"email": user_email},
            {"$set": {"master_id": master_id, "parent_email": parent_email}}
        )

        # ✅ Step 4: Update/create encryption
        encryption_email = request.encryption_email or f"doculan@{new_domain}"
        await encryption_col.update_one(
            {"domain": new_domain},
            {"$set": {"encryption_email": encryption_email}},
            upsert=True
        )

        return {
            "status": "success",
            "user": user_email,
            "new_master_id": master_id,
            "new_parent_email": parent_email,
            "encryption_email": encryption_email,
            "created_new_master": created_new_master
        }

    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )


@router.post("/register", status_code=201)
async def register_user(user: AdminUserCreate):
    try:
        user.parent_email = user.email
        user_id = await AuthService.register_user(user)
        return {"message": "User registered", "user_id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=TokenResponse)
async def login_user(user: UserLogin, response: Response):
    db_user = await AuthService.authenticate_user(user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, subscription_status,  refresh_token= await AuthService.create_token(db_user)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
        path="/"
    )

    # Allow only valid plans in production
    if config.ENV == "prod" and subscription_status.lower() not in ["free","starter", "professional", "enterprise"]:
        raise HTTPException(status_code=403, detail=subscription_status)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        is_temp_password=db_user.get("is_temp_password", False),
        subscription_status=subscription_status
    )

@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    payload = verify_token(refresh_token, scope="refresh_token")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    full_payload = {
        "sub": payload["sub"],
        "id": payload["id"],
        "role": payload["role"],
        "name": payload["name"],
        "user_email": payload["user_email"],
        "email": payload["email"],
        "domain_name": payload["domain_name"],
        "subscription_status": payload["subscription_status"],
        "org": payload["subscription_status"]
    }
    new_access_token = create_access_token(full_payload)
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout", dependencies=[Depends(jwt_bearer)])
def logout(response: Response):
    # Clear refresh token cookie
    response.delete_cookie("refresh_token")  # use the same cookie name set during login
    return {"message": "Logged out"}

@router.post("/forgot-password")
async def forgot_password(email: EmailStr):
    users = db["users"]

    # Find the user
    user = await users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate temporary password
    temp_password = secrets.token_urlsafe(8)
    hashed_temp = security.hash_password(temp_password)

    # Save temporary password and mark flag
    await users.update_one(
        {"email": email},
        {
            "$set": {
                "hashed_password": hashed_temp,
                "is_temp_password": True
            }
        }
    )

    # Prepare email content
    subject = "Password Reset - Temporary Password"
    body = f"""
    <p>Hello {user.get('name', '')},</p>
    <p>Your temporary password is: <b>{temp_password}</b></p>
    <p>Please log in and change your password immediately.</p>
    """

    # Send email using your send_email method
    mailer = EmailService()  # Assuming your send_email is in EmailService class
    mailer.send_email(
        reply_name="Doculan Support",
        reply_email="support@doculan.ai",
        recipient_email=email,
        subject=subject,
        body=body,
        is_html=True,
        cc_emails=None  # Optional CC
    )

    return {"message": "Temporary password sent to your email"}


@router.post("/register-by-admin", status_code=201, dependencies=[Depends(jwt_bearer)])
async def register_user_by_admin(
    user: UserCreateAdmin,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can register new users")

    import secrets
    import string
    generated_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

    user.password = generated_password
    user.created_by = current_user["id"]
    user.parent_email = current_user["email"]
    user.subscription_status = current_user["subscription_status"]

    try:
        user_id = await AuthService.register_user(user, True)
        await email_service.send_credentials_email(user.name, user.email, generated_password, current_user["name"], current_user["email"])
        return {"message": "User registered by admin. Credentials sent via email.", "user_id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/user/preferences", dependencies=[Depends(jwt_bearer)])
async def update_user_preferences(
        preferences: PreferencesUpdate,
        current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]

    if preferences.timezone:
        if not AuthService.validate_timezone(preferences.timezone):
            raise HTTPException(status_code=400, detail="Invalid timezone")

    updated = await AuthService.update_user_preferences(user_id, preferences.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Preferences updated successfully"}

@router.post("/update-password", dependencies=[Depends(jwt_bearer)])
async def update_password(
    new_password: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    # if current_user["role"] == "admin":
    #     raise HTTPException(status_code=403, detail="Admins cannot update password via this endpoint")

    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password too short")

    hashed = security.hash_password(new_password)
    result = await db["users"].update_one(
        {"email": current_user["email"]},
        {"$set": {"hashed_password": hashed, "is_temp_password": False}}
    )

    if result.modified_count:
        return {"message": "Password updated successfully"}
    raise HTTPException(status_code=400, detail="Password update failed")

@router.post("/change-password", dependencies=[Depends(jwt_bearer)])
async def change_password(
    old_password: str = Body(...),
    new_password: str = Body(...),
    current_user: dict = Depends(get_current_user)
):
    # Get user from DB
    user = await db["users"].find_one({"email": current_user["email"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check old password
    if not security.verify_password(old_password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    # Validate new password
    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters long")

    # Update password
    hashed = security.hash_password(new_password)
    result = await db["users"].update_one(
        {"email": current_user["email"]},
        {"$set": {"hashed_password": hashed, "is_temp_password": False}}
    )

    if result.modified_count:
        return {"message": "Password changed successfully"}

    raise HTTPException(status_code=400, detail="Password change failed")


# # ✅ Utility to convert MongoDB object
# def user_helper(user: dict, domain: str = None, encryption_email: str = None) -> dict:
#     return {
#         "id": str(user["_id"]),
#         "email": user.get("email"),
#         "domain": domain,                       # 🔹 added
#         "master_id": user.get("master_id"),
#         "parent_email": user.get("parent_email"),
#         "is_temp_password": user.get("is_temp_password", False),
#         "extra": user.get("extra", {}),
#         "encryption_email": encryption_email,   # 🔹 added
#     }
#
#
# # --------------------------
# # GET ALL USERS
# # --------------------------
# @router.get("/users/deploy/user-get-all", response_model=List[dict])
# async def get_all_users():
#     users_col = db["users"]
#     enc_col = db["encryption"]
#
#     try:
#         users_cursor = users_col.find({})
#         users = []
#
#         async for user in users_cursor:
#             # Extract domain
#             email_domain = user["email"].split("@")[1].lower()
#
#             # Fetch encryption email for that domain
#             enc_doc = await enc_col.find_one({"domain": email_domain})
#             encryption_email = enc_doc["encryption_email"] if enc_doc else None
#
#             # Build user dict with domain + encryption
#             users.append(user_helper(user, email_domain, encryption_email))
#
#         logger.info(f"Fetched {len(users)} users")
#         return users
#
#     except PyMongoError as e:
#         logger.error(f"Failed to fetch users: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to fetch users"
#         ) from e
#
#
#
# class MasterUpdateRequest(BaseModel):
#     master_id: str
# @router.put("/users/{email}/master")
# async def update_user_master(email: EmailStr, body: MasterUpdateRequest):
#     users_col = db["users"]
#
#     try:
#         # Ensure user exists
#         existing_user = await users_col.find_one({"email": email})
#         if not existing_user:
#             logger.warning(f"User with email '{email}' not found for master update")
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail=f"User with email '{email}' not found"
#             )
#
#         # Perform update
#         update_result = await users_col.update_one(
#             {"email": email},
#             {"$set": {"master_id": body.master_id}}
#         )
#
#         if update_result.modified_count == 0:
#             logger.warning(f"Master ID update skipped for '{email}' (no changes)")
#             return {"detail": f"User '{email}' already has master_id '{body.master_id}'"}
#
#         logger.info(f"Updated master_id for '{email}' → {body.master_id}")
#         return {"detail": f"Master ID updated for '{email}'"}
#
#     except PyMongoError as e:
#         logger.error(f"Failed to update master_id for '{email}': {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to update master ID"
#         ) from e
#
#
#
# # --------------------------
# # DELETE USER BY EMAIL
# # --------------------------
# @router.delete("/users/deploy/specific-user", status_code=status.HTTP_200_OK)
# async def delete_user(email: str, code: str):
#     users_col = db["users"]
#     try:
#         if code=="ba2d56d1-6e1c-4a6d-8818-90987fd0e1e8":
#             result = await users_col.delete_one({"email": email})
#             if result.deleted_count == 0:
#                 logger.warning(f"User with email '{email}' not found for deletion")
#                 raise HTTPException(
#                     status_code=status.HTTP_404_NOT_FOUND,
#                     detail=f"User with email '{email}' not found"
#                 )
#             logger.info(f"User '{email}' deleted successfully")
#         else:
#             return {"detail": f"User '{email}' accesss declained successfully"}
#         return {"detail": f"User '{email}' deleted successfully"}
#     except PyMongoError as e:
#         logger.error(f"Failed to delete user '{email}': {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to delete user"
#         ) from e
