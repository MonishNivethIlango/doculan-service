from typing import List, Dict, Optional
from pydantic import BaseModel

from pydantic import BaseModel, EmailStr
from typing import Optional

class CurrentUser(BaseModel):
    id: str
    email: EmailStr
    role: str
    parent_email: EmailStr

class ContentPermission(BaseModel):
    url: str
    content_permissions: Optional[List[str]] = []


class APIPermission(BaseModel):
    method: str
    url: str

class UIPermission(BaseModel):
    page: str
    content_permissions: List[str]
class RoleCreate(BaseModel):
    role_name: str
    api_permissions: List[APIPermission]
    ui_permissions: List[UIPermission]
