from fastapi import APIRouter, UploadFile, File, Query, Form, Depends, HTTPException, status
from typing import List
from starlette.responses import JSONResponse

from DataAccessLayer.storage.storage_factory import get_storage_strategy
from DataAccessLayer.storage.storage_manager import StorageManager
from app.schemas.files_schema import MoveFilesRequest
from app.services.files_service import FileService
from app.services.security_service import EncryptionService, AESCipher
from app.threadsafe.redis_lock import with_redis_lock
from auth_app.app.api.routes.deps import dynamic_permission_check, get_email_from_token, get_user_email_from_token, \
    get_current_user, get_role_from_token
from auth_app.app.model.UserModel import FolderAssignment
from config import config
from database.db_config import S3_user
from database.redis_db import redis_client
from repositories.s3_repo import list_objects_recursive, create_folder_only, delete_folder, get_role_document_ids
from utils.logger import logger

router = APIRouter()

def get_storage(storage_type: str):
    strategy = get_storage_strategy(storage_type)
    return StorageManager(strategy)

def build_folder_hierarchy(path: str, files: list, folderMappingId: str, index: int, root_items: list):

    logger.info(f"Building hierarchy for path='{path}', folderMappingId={folderMappingId}")

    parts = path.split("/")
    current_items = root_items

    for i, part in enumerate(parts):
        # Check if folder already exists at this level
        existing = next(
            (item for item in current_items if item["type"] == "folder" and item["name"] == part),
            None
        )

        if existing:
            node = existing
        else:
            node = {
                "index": index if i == len(parts) - 1 else 1,
                "type": "folder",
                "folderMappingId":"",
                "name": part,
                "items": []
            }

            # Assign folderMappingId at the **root of assigned path**
            if i == 0:
                node["folderMappingId"] = folderMappingId

            current_items.append(node)

        # Leaf handling — attach only files
        if i == len(parts) - 1:
            clean_files = []
            for f in files:
                if f["type"] == "file":
                    clean_files.append(f)
                elif f["type"] == "folder":
                    clean_files.extend(f.get("items", []))
            node["items"] = clean_files
            logger.info(f"Leaf folder created for {part} with files={len(clean_files)} items")

        current_items = node["items"]


@router.get("/files/folder-structure", dependencies=[Depends(dynamic_permission_check)])
def get_s3_structure(
    email: str = Depends(get_email_from_token),
    user_email: str = Depends(get_user_email_from_token),
    role: str = Depends(get_role_from_token)
):
    if role == "admin":
        # Admin can see everything under their files
        prefix = f"{email}/files"
        return {"items": list_objects_recursive(email, prefix)}

    # Non-admin: only allowed folders from user.json
    user_json_key = f"{email}/roles/{role}.json"
    if not S3_user.exists(user_json_key):
        raise HTTPException(
            status_code=404,
            detail="No folder assignment found. Please ask admin to assign folders first."
        )

    try:
        user_data = S3_user.read_json(user_json_key)
        assignment = FolderAssignment(**user_data)   # validate with Pydantic
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read folder assignment: {str(e)}"
        )

    if not assignment.assigned_folders:
        raise HTTPException(
            status_code=403,
            detail="No folders assigned to this user. Please ask admin to update assignments."
        )

    items = []
    index_counter = 1
    for folder_map in assignment.assigned_folders:
        prefix = f"{email}/files/{folder_map.path}"

        # Build only this folder structure
        folder_items = list_objects_recursive(email, prefix)

        if folder_items:
            # Take the first folder node and inject folderMappingId
            root_folder = folder_items[0]
            root_folder["folderMappingId"] = folder_map.folderMappingId
            root_folder["index"] = index_counter
            items.append(root_folder)

    # Wrap in "files" root
    return {
        "items": [
            {
                "index": 1,
                "type": "folder",
                "name": "files",
                "items": items
            }
        ]
    }


@router.post("/files/upload/", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="upload:{path}", ttl=15)
async def upload_files(
    files: List[UploadFile] = File(...),
    path: str = Form(None),
    overwrite: bool = Form(False),
    email: str = Depends(get_email_from_token), current_user: dict = Depends(get_current_user), user_email: str = Depends(get_user_email_from_token)
):
    # Validate all files are PDFs
    invalid_files = [
        file.filename for file in files
        if not (file.content_type == "application/pdf" or file.filename.lower().endswith(".pdf"))
    ]

    if invalid_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Only PDF files are allowed.",
                "invalid_files": invalid_files
            }
        )
    name = current_user.get("name")

    storage = get_storage(config.STORAGE_TYPE)
    file_service = FileService(storage)
    results = await file_service.files_upload(email, user_email, name, files, path, overwrite)
    return {"uploaded_files": results}

@router.get("/files/{document_id}", dependencies=[Depends(dynamic_permission_check)])
async def get_file(
    document_id: str,
    return_pdf: bool = Query(False, description="Return PDF file if true, otherwise return metadata"),
    email: str = Depends(get_email_from_token)
):
    storage = get_storage(config.STORAGE_TYPE)
    encryption_service = EncryptionService()
    encryption_email = await encryption_service.resolve_encryption_email(email)
    cipher = AESCipher(encryption_email)
    result = storage.get(cipher, email, document_id=document_id, return_pdf=return_pdf)

    if isinstance(result, dict) and result.get("error"):
        return JSONResponse(status_code=404, content=result)

    file_service = FileService(storage)
    return await file_service.get_pdf(result, return_pdf)

@router.get("/files/", dependencies=[Depends(dynamic_permission_check)])
async def list_files(
    email: str = Depends(get_email_from_token),
    user_email: str = Depends(get_user_email_from_token),
    role: str = Depends(get_role_from_token),
):
    storage = get_storage(config.STORAGE_TYPE)
    from auth_app.app.services.auth_service import auth_service
    email = await auth_service.get_domain_if_master(email)

    storage = get_storage(config.STORAGE_TYPE)
    encryption_service = EncryptionService()
    encryption_email = await encryption_service.resolve_encryption_email(email)

    cipher = AESCipher(encryption_email)
    logger.info(f"file get {email}")

    # Admin: return all files under /files
    if role == "admin":
        folder_prefix = f"{email}/files"
        return storage.list(email, folder_prefix)

    # Non-admin: check user assignment
    user_json_key = f"{email}/roles/{role}.json"
    if not S3_user.exists(user_json_key):
        raise HTTPException(
            status_code=404,
            detail="No folder assignment found. Please ask admin to assign folders first.",
        )

    try:
        user_data = S3_user.read_json(user_json_key)
        assignment = FolderAssignment(**user_data)  # validate with Pydantic
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read folder assignment: {str(e)}",
        )

    if not assignment.assigned_folders:
        raise HTTPException(
            status_code=403,
            detail="No folders assigned to this user. Please ask admin to update assignments.",
        )

    all_files = []
    for folder_map in assignment.assigned_folders:
        prefix = f"{email}/files/{folder_map.path}"
        folder_files = storage.list(email, prefix).get("files", [])
        all_files.extend(folder_files)

    return {"files": all_files}


@router.delete("/files/{document_id}", dependencies=[Depends(dynamic_permission_check)])
async def delete_file(document_id: str, email: str = Depends(get_email_from_token)):
    storage = get_storage(config.STORAGE_TYPE)
    return storage.delete(email, document_id)

@router.put("/files/{document_id}", dependencies=[Depends(dynamic_permission_check)])
async def update_file(document_id: str, new_file: UploadFile, email: str = Depends(get_email_from_token)):
    storage = get_storage(config.STORAGE_TYPE)
    return storage.update(email, document_id, new_file)

@router.put("/files/move/", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="move:{new_folder}", ttl=10)
async def move_files(request: MoveFilesRequest, email: str = Depends(get_email_from_token), current_user: dict = Depends(get_current_user), user_email: str = Depends(get_user_email_from_token)):
    storage = get_storage(config.STORAGE_TYPE)
    if not request.document_ids:
        name = current_user.get("name")
        result = create_folder_only(email=email, new_folder=request.new_folder, name=name, user_email=user_email, )
    else:
        result = storage.move(email=email, document_ids=request.document_ids, new_folder=request.new_folder)
    return result

@router.delete("/files/folders/", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="folder_delete:{folder_name}", ttl=10)
async def delete_folders(folder_name: str, email: str = Depends(get_email_from_token)):
    result = delete_folder(email=email, folder_name=folder_name)
    return result


# @router.get("/files/{role}/document-names", dependencies=[Depends(dynamic_permission_check)])
# def get_role_document_trackings(role: str, email: str = Depends(get_email_from_token)):
#     # Step 1: Get document IDs using your existing function
#     docs_response = get_role_document_ids(role, email)
#     document_ids = docs_response.get("documentIds", []) or docs_response.get("documentNames", [])
#
#     results = {}
#
#     # Step 2: For each document, look inside its tracking folder
#     logger.info(document_ids)
#     for doc_id in document_ids:
#         prefix = f"{email}/metadata/tracking/{doc_id}/"
#         tracking_ids = []
#         logger.info(tracking_ids)
#         logger.info(prefix)
#
#
#         # List all objects under metadata/tracking/{doc_id}/
#         try:
#             tracking_objects = S3_user.list(prefix)  # ✅ use S3 metadata list
#             for obj in tracking_objects:
#                 if obj.endswith(".json"):
#                     tracking_id = obj.rsplit("/", 1)[-1].replace(".json", "")
#                     tracking_ids.append(tracking_id)
#         except Exception as e:
#             tracking_ids = []
#
#         results[doc_id] = tracking_ids
#
#     return {
#         "documentIds": document_ids,
#         "trackings": results
#     }



