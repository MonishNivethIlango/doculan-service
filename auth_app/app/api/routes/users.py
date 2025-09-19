import uuid
from typing import List, Optional

from auth_app.app.api.routes.deps import get_current_user, dynamic_permission_check, get_email_from_token, \
    get_user_email_from_token
from auth_app.app.database.connection import db
from auth_app.app.model.UserModel import UserSignature, UpdateSignatureRequest, FolderAssignment, generate_folder_id
from auth_app.app.repository.user import UserCRUD
from auth_app.app.schema.UserSchema import UserUpdate, UserOut, RoleAssignment, UserOutAdminUser
from fastapi import APIRouter, Depends, HTTPException, Body

from database.db_config import S3_user

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/current-user", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@router.get("/get-all-user", dependencies=[Depends(dynamic_permission_check)])
async def get_all_users():
    users = await UserCRUD.get_all_users()
    for user in users:
        user["id"] = str(user["_id"])
        del user["_id"]
    return users

@router.get("/get-my-users", response_model=List[UserOutAdminUser], dependencies=[Depends(dynamic_permission_check)])
async def get_users_created_by_me(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can access this endpoint")

    users_cursor = db["users"].find({"created_by": current_user["id"]})
    users = await users_cursor.to_list(length=1000)  # limit results as needed

    # Convert MongoDB _id to id
    for user in users:
        user["id"] = str(user["_id"])
        del user["_id"]

    return users

@router.get("/{user_email}", dependencies=[Depends(dynamic_permission_check)])
async def get_user(user_email: str):
    user = await UserCRUD.get_user_by_email(user_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_email}", dependencies=[Depends(dynamic_permission_check)])
async def update_user(user_email: str, user_data: UserUpdate):
    updated = await UserCRUD.update_user_by_email(user_email, user_data)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found or not updated")
    return {"message": "User updated successfully"}

@router.delete("/{user_email}", dependencies=[Depends(dynamic_permission_check)])
async def delete_user(user_email: str):
    deleted = await UserCRUD.deactivate_user_by_email(user_email)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}



@router.put("/assign-role", dependencies=[Depends(dynamic_permission_check)])
def assign_role_to_user(payload: RoleAssignment):
    result = db["users"].update_one(
        {"email": payload.email},
        {"$set": {"role": payload.role}}
    )

    if result.modified_count == 0:
        return {"msg": "User not found or roles unchanged"}
    return {"msg": "Roles assigned to user"}



@router.post("/signatures/upload", dependencies=[Depends(dynamic_permission_check)])
async def upload_signatures(
    signatures: List[UserSignature],
    email: str = Depends(get_user_email_from_token)
):
    # Fetch existing signatures
    doc = await db["esignature"].find_one({"email": email})
    existing_sigs = doc.get("signatures", []) if doc else []

    new_signatures = []
    for sig in signatures:
        sig_data = {
            "id": str(uuid.uuid4()),
            "name": sig.name,
            "type": sig.type,
            "value": sig.value,
            "isDefault": sig.isDefault,
        }
        new_signatures.append(sig_data)
        existing_sigs.append(sig_data)

    # Update DB
    result = await db["esignature"].update_one(
        {"email": email},
        {"$set": {"signatures": existing_sigs}},
        upsert=True
    )

    return {
        "msg": "Signatures added",
        "modified": result.modified_count,
        "upserted": result.upserted_id is not None,
        "added_signatures": new_signatures
    }


# ---- GET: Fetch signatures ----
@router.get("/signatures/get", dependencies=[Depends(dynamic_permission_check)])
async def get_signatures(email: str,
    name: Optional[str] = None,

):
    doc = await db["esignature"].find_one(
        {"email": email},
        {"_id": 0, "signatures": 1}
    )

    if not doc or "signatures" not in doc:
        return {"msg": "No signatures found", "signatures": []}

    signatures = doc["signatures"]
    if not isinstance(signatures, list):
        raise HTTPException(status_code=400, detail="Invalid signature data format")

    # filter out malformed entries
    valid_signatures = [s for s in signatures if isinstance(s, dict) and "name" in s]

    if name:
        sig = next((s for s in valid_signatures if s.get("name") == name), None)
        if not sig:
            raise HTTPException(
                status_code=404,
                detail=f"Signature with name '{name}' not found"
            )
        return {"signature": sig}

    return {"signatures": valid_signatures}


# ---- DELETE: Delete all or one signature ----
@router.delete("/signatures/delete", dependencies=[Depends(dynamic_permission_check)])
async def delete_signatures(
    name: Optional[str] = None,
    email: str = Depends(get_user_email_from_token)
):
    doc = await db["esignature"].find_one({"email": email})
    if not doc or "signatures" not in doc:
        raise HTTPException(status_code=404, detail="No signatures found")

    signatures = doc["signatures"]
    if not isinstance(signatures, list):
        raise HTTPException(status_code=400, detail="Invalid signature data format")

    if name is None:
        # Delete all signatures
        result = await db["esignature"].update_one(
            {"email": email},
            {"$unset": {"signatures": ""}}
        )
        return {"msg": "All signatures deleted", "modified": result.modified_count}

    # Delete only those that have a "name" and don't match
    updated_sigs = [s for s in signatures if isinstance(s, dict) and s.get("name") != name]

    if len(updated_sigs) == len(signatures):
        raise HTTPException(status_code=404, detail=f"Signature with name '{name}' not found")

    result = await db["esignature"].update_one(
        {"email": email},
        {"$set": {"signatures": updated_sigs}}
    )
    return {"msg": f"Signature '{name}' deleted", "modified": result.modified_count}


# ---- GET: Fetch all signatures ----
@router.get("/signatures/get-all", dependencies=[Depends(dynamic_permission_check)])
async def get_all_signatures(email: str):
    doc = await db["esignature"].find_one({"email": email}, {"_id": 0, "signatures": 1})
    if not doc or "signatures" not in doc:
        return {"msg": "No signatures found", "signatures": []}
    return {"signatures": doc["signatures"]}


# ---- PATCH: Update signature (only name & isDefault) ----
@router.put("/signatures/update", dependencies=[Depends(dynamic_permission_check)])
async def update_signature(
    update_req: UpdateSignatureRequest,
    email: str = Depends(get_user_email_from_token)
):
    # Fetch user signature document
    doc = await db["esignature"].find_one({"email": email})
    if not doc or "signatures" not in doc:
        raise HTTPException(status_code=404, detail="No signatures found")

    signatures = doc["signatures"]
    if not isinstance(signatures, list):
        raise HTTPException(status_code=400, detail="Invalid signature data format")

    updated = False

    # Iterate safely through signatures
    for sig in signatures:
        if not isinstance(sig, dict) or "name" not in sig:
            continue  # skip malformed entries

        if sig.get("name") == update_req.old_name:
            if update_req.new_name:
                sig["name"] = update_req.new_name
                updated = True

            if update_req.isDefault is not None:
                if update_req.isDefault:
                    # reset all signatures' default
                    for s in signatures:
                        if isinstance(s, dict):
                            s["isDefault"] = False
                sig["isDefault"] = update_req.isDefault
                updated = True
            break

    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"Signature '{update_req.old_name}' not found or no valid update fields provided"
        )

    # Persist the update
    result = await db["esignature"].update_one(
        {"email": email},
        {"$set": {"signatures": signatures}}
    )

    return {
        "msg": "Signature updated successfully",
        "modified": result.modified_count,
        "signatures": signatures
    }



