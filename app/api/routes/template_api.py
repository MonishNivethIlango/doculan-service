from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.template_schema import (
    TemplateCreate,
    TemplateUpdate
)
from app.services.template_service import TemplateManager
from app.threadsafe.redis_lock import with_redis_lock
from auth_app.app.api.routes.deps import get_email_from_token, dynamic_permission_check, get_user_email_from_token
from database.redis_db import redis_client

router = APIRouter()


@router.get("/templates/{template_name}", dependencies=[Depends(dynamic_permission_check)])
def get(template_name: str, is_global: bool = Query(False), email: str = Depends(get_email_from_token) , user_email: str = Depends(get_user_email_from_token) ):
    templateManager = TemplateManager(email, user_email)
    return templateManager.get_template(template_name, is_global)


@router.delete("/templates/{template_name}", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="template:delete:{template_name}", ttl=10)
def delete(template_name: str, is_global: bool = Query(False), email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    templateManager = TemplateManager(email, user_email)
    return templateManager.delete_template(template_name, is_global)

@router.put("/templates/{template_name}", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="template:update:{template_name}", ttl=10)
def update_template_api(template_name: str, data: TemplateUpdate, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    templateManager = TemplateManager(email, user_email)
    return templateManager.update_template(data, template_name, data.fields, data.parties, data.is_global)

@router.post("/templates", dependencies=[Depends(dynamic_permission_check)])
@with_redis_lock(redis_client, lock_key_template="template:create:{template_name}", ttl=10)
def create(data: TemplateCreate, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    templateManager = TemplateManager(email, user_email)
    return templateManager.create_template(data, data.template_name, data.fields, data.parties, data.is_global)

@router.get("/templates", dependencies=[Depends(dynamic_permission_check)])
def get_all(is_global: Optional[bool] = Query(None), email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    templateManager = TemplateManager(email, user_email)
    if is_global is None:
        return templateManager.get_all_templates()
    return templateManager.load_all_templates(is_global=is_global)
