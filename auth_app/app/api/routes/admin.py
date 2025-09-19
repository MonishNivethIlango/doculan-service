from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_app.app.api.routes.deps import dynamic_permission_check, get_email_from_token, get_user_email_from_token, \
    get_role_from_token, get_org_from_token
from auth_app.app.model.UserModel import generate_folder_id, FolderAssignment, FolderMapping

from auth_app.app.schema.RoleSchema import RoleCreate

from auth_app.app.database.connection import db
from config import config
from database.db_config import S3_user, s3_client
from utils.logger import logger

admin_router = APIRouter()

@admin_router.get("/routes/grouped", dependencies=[Depends(dynamic_permission_check)])
async def get_routes_grouped_by_tag():
    routes = await db.routes.find().to_list(None)
    grouped = {}

    for route in routes:
        tags = route.get("tags", ["Untagged"])
        route_entry = {
            "path": route["path"],
            "method": route["method"],
            "name": route["name"]
        }

        for tag in tags:
            grouped.setdefault(tag, [])

            # Check for duplication before appending
            if route_entry not in grouped[tag]:
                grouped[tag].append(route_entry)

    return grouped

@admin_router.post("/roles", dependencies=[Depends(dynamic_permission_check)])
async def create_org_role(role_data: RoleCreate, org: str = Depends(get_org_from_token)):
    if not org:
        raise HTTPException(status_code=400, detail="Org context required to create roles")

    org_doc = await db.org_roles.find_one({"org_name": org})

    if org_doc:
        # ✅ Fail if role already exists
        if any(r["role_name"] == role_data.role_name for r in org_doc["roles"]):
            raise HTTPException(
                status_code=409,  # Conflict
                detail=f"Role '{role_data.role_name}' already exists in org '{org}'"
            )

        # Append new role
        org_doc["roles"].append({
            "role_name": role_data.role_name,
            "api_permissions": [perm.dict() for perm in role_data.api_permissions],
            "ui_permissions": [perm.dict() for perm in role_data.ui_permissions]
        })
        await db.org_roles.update_one({"org_name": org}, {"$set": {"roles": org_doc["roles"]}})
    else:
        # Create new org document with first role
        await db.org_roles.insert_one({
            "org_name": org,
            "roles": [{
                "role_name": role_data.role_name,
                "api_permissions": [perm.dict() for perm in role_data.api_permissions],
                "ui_permissions": [perm.dict() for perm in role_data.ui_permissions]
            }]
        })

    return {"msg": f"Role '{role_data.role_name}' created successfully"}


@admin_router.put("/roles/{role_name}", dependencies=[Depends(dynamic_permission_check)])
async def update_org_role(
    role_name: str,
    role_data: RoleCreate,
    org: str = Depends(get_org_from_token)
):
    if not org:
        raise HTTPException(status_code=400, detail="Org context required to update roles")

    org_doc = await db.org_roles.find_one({"org_name": org})
    if not org_doc:
        raise HTTPException(status_code=404, detail=f"Organization '{org}' not found")

    updated = False
    for r in org_doc["roles"]:
        if r["role_name"] == role_name:
            r["api_permissions"] = [perm.dict() for perm in role_data.api_permissions]
            r["ui_permissions"] = [perm.dict() for perm in role_data.ui_permissions]
            updated = True
            break

    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"Role '{role_name}' not found in org '{org}'"
        )

    await db.org_roles.update_one({"org_name": org}, {"$set": {"roles": org_doc["roles"]}})
    return {"msg": f"Role '{role_name}' updated successfully"}



@admin_router.get("/roles", dependencies=[Depends(dynamic_permission_check)])
async def get_all_roles(org: str = Depends(get_org_from_token)):
    roles_list = []

    # Default roles
    async for role in db.default_roles.find():
        roles_list.append(convert_objectid(role))

    # Org-specific roles
    if org:
        org_doc = await db.org_roles.find_one({"org_name": org})
        if org_doc and "roles" in org_doc:
            roles_list.extend(org_doc["roles"])

    return roles_list

@admin_router.get("/roles/{role_name}", dependencies=[Depends(dynamic_permission_check)])
async def get_role(role_name: str, org: str = Depends(get_org_from_token)):
    # First check org roles
    if org:
        org_doc = await db.org_roles.find_one({"org_name": org})
        if org_doc:
            for r in org_doc.get("roles", []):
                if r["role_name"] == role_name:
                    return r

    # Then check default roles
    role = await db.default_roles.find_one({"role_name": role_name}, {"_id": 0})
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")

    return role

@admin_router.delete("/roles/{role_name}", dependencies=[Depends(dynamic_permission_check)])
async def delete_org_role(role_name: str, org: str = Depends(get_org_from_token)):
    if not org:
        raise HTTPException(status_code=400, detail="Org context required to delete roles")

    org_doc = await db.org_roles.find_one({"org_name": org})
    if not org_doc or role_name not in [r["role_name"] for r in org_doc.get("roles", [])]:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found in org")

    updated_roles = [r for r in org_doc["roles"] if r["role_name"] != role_name]
    await db.org_roles.update_one({"org_name": org}, {"$set": {"roles": updated_roles}})
    return {"msg": f"Role '{role_name}' deleted successfully"}


def convert_objectid(role):
    role["_id"] = str(role["_id"])
    return role

@admin_router.get("/roles", dependencies=[Depends(dynamic_permission_check)])
async def get_all_roles(org: str = Depends(get_org_from_token)):
    roles_list = []

    # 1️⃣ Add default roles
    async for role in db.default_roles.find():
        roles_list.append(convert_objectid(role))

    # 2️⃣ Add org-specific roles if org is provided
    if org:
        org_doc = await db.org_roles.find_one({"org_name": org})
        if org_doc and "roles" in org_doc:
            for role in org_doc["roles"]:
                roles_list.append(role)

    return roles_list


@admin_router.get("/permission-matrix", dependencies=[Depends(dynamic_permission_check)])
async def get_permission_matrix():
    roles = await db.roles.find().to_list(None)
    routes = await db.routes.find().to_list(None)

    matrix = []

    for route in routes:
        row = {
            "path": route["path"],
            "method": route["method"],
            "tags": route.get("tags", []),
        }

        for role in roles:
            allowed = any(
                p["method"] == route["method"] and p["path"] == route["path"]
                for p in role.get("permissions", [])
            )
            row[role["name"]] = allowed

        matrix.append(row)

    return matrix





# ---------- Reusable S3 Functions ----------
def get_role_key(admin_email: str, role_name: str) -> str:
    return f"{admin_email}/roles/{role_name}.json"


def read_role_assignment(admin_email: str, role_name: str) -> dict:
    key = get_role_key(admin_email, role_name)
    if not S3_user.exists(key):
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")
    return S3_user.read_json(key)


def write_role_assignment(admin_email: str, role_name: str, folders: List[FolderMapping]) -> dict:
    # Ensure folderMappingIds are unique and generated if missing
    seen_ids = set()
    folder_list = []
    for f in folders:
        if not f.folderMappingId:
            f.folderMappingId = generate_folder_id()
        if f.folderMappingId in seen_ids:
            raise HTTPException(status_code=400, detail=f"Duplicate folderMappingId: {f.folderMappingId}")
        seen_ids.add(f.folderMappingId)
        folder_list.append(f.dict())
    payload = {"role_name": role_name, "assigned_folders": folder_list}
    S3_user.write_json(get_role_key(admin_email, role_name), payload)
    return payload


def delete_role_assignment(admin_email: str, role_name: str):
    key = get_role_key(admin_email, role_name)
    if not S3_user.exists(key):
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")
    S3_user.delete_object(key)
# ---------- Utility ----------
def list_all_roles(admin_email: str) -> List[dict]:
    """
    List all role assignments for the given admin.
    """
    prefix = f"{admin_email}/roles/"
    response = s3_client.list_objects(Bucket=config.S3_BUCKET, Prefix=prefix)

    if not response or "Contents" not in response:
        return []

    roles = []
    for obj in response["Contents"]:
        key = obj["Key"]
        if key.endswith(".json"):
            try:
                roles.append(S3_user.read_json(key))
            except Exception as e:
                print(f"Warning: could not read {key}: {e}")
                continue
    return roles


# ---------- CRUD Endpoints ----------
@admin_router.get("/roles/folders/get-all", dependencies=[Depends(dynamic_permission_check)])
def get_all_role_folders(admin_email: str = Depends(get_email_from_token)):
    """
    Get all role folder assignments for an admin
    """
    logger.info(f"admin email{admin_email}")
    roles = list_all_roles(admin_email)
    return {"count": len(roles), "roles": roles}


# ---------- CRUD Endpoints ----------
@admin_router.get("/roles/folders/{role_name}", dependencies=[Depends(dynamic_permission_check)])
def get_role_folders(role: str ,admin_email: str = Depends(get_email_from_token)):
    """
    Get folder assignment for a specific role
    """
    return read_role_assignment(admin_email, role)


@admin_router.post("/roles/folders", dependencies=[Depends(dynamic_permission_check)])
def create_role_folders(data: FolderAssignment, admin_email: str = Depends(get_email_from_token)):
    """
    Create folder assignment for a role
    """
    key = get_role_key(admin_email, data.role_name)
    if S3_user.exists(key):
        raise HTTPException(status_code=400, detail=f"Role '{data.role_name}' already exists")
    payload = write_role_assignment(admin_email, data.role_name, data.assigned_folders)
    return {"message": "Role folder assignment created", "data": payload}


@admin_router.put("/roles/folders/update", dependencies=[Depends(dynamic_permission_check)])
def update_role_folders(data: FolderAssignment, admin_email: str = Depends(get_email_from_token)):
    """
    Update/replace folder assignment for a role
    """
    payload = write_role_assignment(admin_email, data.role_name, data.assigned_folders)
    return {"message": "Role folder assignment updated", "data": payload}


@admin_router.delete("/roles/folders/{role_name}", dependencies=[Depends(dynamic_permission_check)])
def delete_role_folders(role_name: str, admin_email: str = Depends(get_email_from_token)):
    """
    Delete folder assignment for a role
    """
    delete_role_assignment(admin_email, role_name)
    return {"message": f"Role '{role_name}' folder assignment deleted"}


@admin_router.delete("/roles/folders/{role_name}/{folder_id}", dependencies=[Depends(dynamic_permission_check)])
def delete_role_folder(role_name: str, folder_id: str, admin_email: str = Depends(get_email_from_token)):
    """
    Delete a single folder from a role's assignment
    """
    role_data = read_role_assignment(admin_email, role_name)
    assigned_folders = role_data.get("assigned_folders", [])
    updated_folders = [f for f in assigned_folders if f["folderMappingId"] != folder_id]

    if len(updated_folders) == len(assigned_folders):
        raise HTTPException(status_code=404, detail=f"Folder ID '{folder_id}' not found in role '{role_name}'")

    # Update S3
    role_data["assigned_folders"] = updated_folders
    S3_user.write_json(get_role_key(admin_email, role_name), role_data)

    return {
        "message": f"Folder ID '{folder_id}' removed from role '{role_name}'",
        "remaining_folders": updated_folders
    }

