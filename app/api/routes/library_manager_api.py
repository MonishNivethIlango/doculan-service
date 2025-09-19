import uuid

from fastapi import APIRouter, UploadFile, File, Query, Form, Depends, HTTPException, status
from typing import List
from starlette.responses import JSONResponse
from DataAccessLayer.library_storage.storage_library_factory import get_storage_library_strategy
from DataAccessLayer.library_storage.storage_manager import LibraryStorageManager
from app.schemas.form_schema import RegistrationForm, RegistrationLibraryForm
from app.schemas.libraries_schema import MoveLibrariesRequest
from app.schemas.template_schema import TemplateLibrariesCreate, TemplateLibrariesUpdate
from app.services.library_service import LibraryService, TemplateLibraryManager, LibraryFormService
from app.services.security_service import AESCipher, EncryptionService
from app.threadsafe.redis_lock import with_redis_lock
from auth_app.app.api.routes.deps import dynamic_permission_check, get_email_from_token, get_user_email_from_token
from config import config
from database.redis_db import redis_client
from repositories.s3_repo import list_objects_recursive, delete_library_folder, \
    create_folder, get_json

router = APIRouter()

def get_storage(storage_type: str):
    strategy = get_storage_library_strategy(storage_type)
    return LibraryStorageManager(strategy)

# 📂 Get folder structure for libraries
@router.get("/libraries/folder-structure", dependencies=[Depends(dynamic_permission_check)])
def get_s3_structure(email: str = Depends(get_email_from_token)):
    return {"items": list_objects_recursive(email, f"{email}/libraries")}

# ⬆ Upload library PDFs
@router.post("/libraries/upload/", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="upload:{path}", ttl=15)
async def upload_libraries(
    files: List[UploadFile] = File(...),
    path: str = Form(None),
    overwrite: bool = Form(False),
    email: str = Depends(get_email_from_token),
):
    # Validate only PDFs


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

    storage = get_storage(config.STORAGE_TYPE)
    library_service = LibraryService(storage)
    results = await library_service.library_upload(email, files, path, overwrite)
    return {"uploaded_libraries": results}

# 📄 Get library document
@router.get("/libraries/{library_id}", dependencies=[Depends(dynamic_permission_check)])
async def get_library(
    library_id: str,
    return_pdf: bool = Query(False, description="Return PDF if true, otherwise metadata"),
    email: str = Depends(get_email_from_token)
):
    storage = get_storage(config.STORAGE_TYPE)
    encryption_service = EncryptionService()
    encryption_email = await encryption_service.resolve_encryption_email(email)
    cipher = AESCipher(encryption_email)
    result = storage.get_library(cipher, email, library_id=library_id, return_pdf=return_pdf)

    if isinstance(result, dict) and result.get("error"):
        return JSONResponse(status_code=404, content=result)

    library_service = LibraryService(storage)
    return await library_service.get_document(result, return_pdf)

# 📋 List libraries
@router.get("/libraries/", dependencies=[Depends(dynamic_permission_check)])
async def list_libraries(email: str = Depends(get_email_from_token)):
    storage = get_storage(config.STORAGE_TYPE)
    return storage.list_libraries()

# 🗑 Delete library
@router.delete("/libraries/{library_id}", dependencies=[Depends(dynamic_permission_check)])
async def delete_library(library_id: str, email: str = Depends(get_email_from_token)):
    storage = get_storage(config.STORAGE_TYPE)
    return storage.delete_library(email, library_id)

# ✏ Update library
@router.put("/libraries/{library_id}", dependencies=[Depends(dynamic_permission_check)])
async def update_library(library_id: str, new_file: UploadFile, email: str = Depends(get_email_from_token)):
    storage = get_storage(config.STORAGE_TYPE)
    return storage.update_library(email, library_id, new_file)

# 📂 Move libraries or create folder
@router.put("/libraries/move/", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="move:{new_folder}", ttl=10)
async def move_libraries(request: MoveLibrariesRequest, email: str = Depends(get_email_from_token)):
    storage = get_storage(config.STORAGE_TYPE)
    if not request.library_ids:
        result = create_folder(email=email, new_folder=request.new_folder)
    else:
        result = storage.move_library(email=email, library_ids=request.library_ids, new_folder=request.new_folder)
    return result

# 🗑 Delete library folder
@router.delete("/libraries/folders/", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="folder_delete:{folder_name}", ttl=10)
async def delete_library_folders(folder_name: str, email: str = Depends(get_email_from_token)):
    result = delete_library_folder(email=email, folder_name=folder_name)
    return result

@router.get("/libraries/templates/{template_name}", dependencies=[Depends(dynamic_permission_check)])
def get_template(template_name: str, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    templateManager = TemplateLibraryManager(email, user_email)
    return templateManager.get_template(template_name)


@router.delete("/libraries/templates/{template_name}", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="library:template:delete:{template_name}", ttl=10)
def delete_template(template_name: str, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    templateManager = TemplateLibraryManager(email, user_email)
    return templateManager.delete_template(template_name)


@router.put("/libraries/templates/{template_name}", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="library:template:update:{template_name}", ttl=10)
def update_template(template_name: str, data: TemplateLibrariesUpdate, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    templateManager = TemplateLibraryManager(email, user_email)
    return templateManager.update_template(data, template_name, data.fields, data.parties)


@router.post("/libraries/templates", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="library:template:create:{template_name}", ttl=10)
def create_template(data: TemplateLibrariesCreate, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    templateManager = TemplateLibraryManager(email, user_email)
    return templateManager.create_template(data, data.template_name, data.fields, data.parties)


@router.get("/libraries/templates-all", dependencies=[Depends(dynamic_permission_check)])
def list_templates(email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    templateManager = TemplateLibraryManager(email, user_email)
    return templateManager.get_all_templates()


@router.post("/libraries/forms/", dependencies=[Depends(dynamic_permission_check)])
async def create_library_form(form: RegistrationLibraryForm, email: str = Depends(get_email_from_token)):
    formService = LibraryFormService()
    library_form_id = str(uuid.uuid4())
    formService.save_form(library_form_id, data=form.dict())
    return {"message": "Form saved successfully", "library_form_id": library_form_id}


@router.get("/libraries/forms/{library_form_id}", dependencies=[Depends(dynamic_permission_check)])
async def get_library_form(library_form_id: str, email: str = Depends(get_email_from_token)):
    formService = LibraryFormService()
    form_data = formService.get_form(library_form_id)
    if not form_data:
        raise HTTPException(status_code=404, detail="Form not found")
    return form_data


@router.get("/libraries/forms/", dependencies=[Depends(dynamic_permission_check)])
async def get_all_library_forms(email: str = Depends(get_email_from_token)):
    formService = LibraryFormService()
    forms = formService.list_forms()
    return {"forms": forms}


@router.put("/libraries/forms/{library_form_id}", dependencies=[Depends(dynamic_permission_check)])
async def update_library_form(library_form_id: str, form: RegistrationForm, email: str = Depends(get_email_from_token)):
    formService = LibraryFormService()
    if not formService.get_form(library_form_id):
        raise HTTPException(status_code=404, detail="Form not found")
    formService.update_form(library_form_id, form.dict())
    return {"message": "Form updated successfully"}


@router.delete("/libraries/forms/{library_form_id}", dependencies=[Depends(dynamic_permission_check)])
async def delete_library_form(library_form_id: str, email: str = Depends(get_email_from_token)):
    formService = LibraryFormService()
    if not formService.get_form(library_form_id):
        raise HTTPException(status_code=404, detail="Form not found")
    formService.delete_form(library_form_id)
    return {"message": "Form deleted successfully"}

@router.get("/libraries/forms/tag", dependencies=[Depends(dynamic_permission_check)])
async def get_forms_by_tag(tag_name: str):
    tags_key = "metadata/library/tags.json"
    tags_json = get_json(tags_key) or {}

    if tag_name not in tags_json:
        raise HTTPException(status_code=404, detail=f"No forms found for tag '{tag_name}'")

    forms = []
    for entry in tags_json[tag_name]:
        form_id = entry["formId"]
        form_key = f"metadata/library/forms/{form_id}.json"
        form_data = get_json(form_key)
        if form_data:
            forms.append(form_data)

    return {"tag": tag_name, "forms": forms}
