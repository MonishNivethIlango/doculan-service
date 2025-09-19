# app/schemas/user.py

from typing import Literal, Optional, Any, Dict, List
from pydantic import BaseModel, EmailStr, Field
from pydantic.v1 import constr

from auth_app.app.schema.AuthSchema import PreferencesUpdate

# Role and Status values
RoleType = str
StatusType = Literal["active", "inactive"]

class Address(BaseModel):
    address_line_1: str
    address_line_2: Optional[str]
    city: str
    country: Optional[str]
    state: str
    zipcode: str


from typing import List

class ESignHistoryItem(BaseModel):
    year: int
    month: int
    month_name: str
    send_count: int
    is_current_month: bool

class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    status: str
    preferences: Optional[PreferencesUpdate] = None
    folder_size_bytes: Optional[int] = None
    folder_size_mb: Optional[float] = None
    subscription_status: str
    address: Optional[Address] = None
    organization: Optional[str] = None
    monthly_limit: Optional[str] = None
    remaining_e_signs: Optional[str] = None
    total_send_count: Optional[str] = None
    current_month_count: Optional[str] = None
    history: Optional[List[ESignHistoryItem]] = None
    theme: Optional[str] = None
    dark_theme: Optional[bool] = False
    logo: Optional[str] = None
    user_logo: Optional[str] = None
    dynamic_fields: Optional[Dict[str, Optional[str]]] = None



class UserOutAdminUser(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    status: str
    preferences: Optional[PreferencesUpdate] = None
    # subscription_status: Optional[str]
    organization: Optional[str] = None
    logo: Optional[str] = None
    theme: Optional[str] = None
    dynamic_fields: Optional[Dict[str, Optional[str]]] = None

class UserOutWithID(UserOut):
    id: str

    class Config:
        from_attributes  = True


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: RoleType
    status: StatusType
    password: Optional[str]
    parent_email: Optional[EmailStr] = None
    created_by: Optional[str] = None
    preferences: Optional[PreferencesUpdate] = None
    subscription_status: Optional[str]
    address: Optional[Address]
    organization: Optional[str] = None
    logo: Optional[str]
    theme: Optional[str]
    extra: Optional[Dict[str, Any]] = {}

    class Config:
        extra = "allow"
class AdminUserCreate(BaseModel):
    name: str
    email: EmailStr
    role: RoleType
    status: StatusType
    password: Optional[str]
    parent_email: Optional[EmailStr] = None
    created_by: Optional[str] = None
    preferences: Optional[PreferencesUpdate] = None
    subscription_status: Optional[str]
    organization: Optional[str] = None
    logo: Optional[str]
    theme: Optional[str]
    extra: Optional[Dict[str, Any]] = {}

    class Config:
        extra = "allow"


class UserCreateAdmin(UserCreate):
    pass

class RoleAssignment(BaseModel):
    email: EmailStr
    role: str



class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    role: Optional[RoleType]
    status: Optional[StatusType]
    password: Optional[str]
    logo: Optional[str]
    user_logo: Optional[str]
    theme: Optional[str]
    dark_theme: Optional[bool]
    address: Optional[Address]

    class Config:
        extra = "allow"


