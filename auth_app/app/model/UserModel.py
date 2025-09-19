# app/models/UserModel.py
from nanoid import generate

from typing import Optional, Literal, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class MongoUser(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    email: EmailStr
    role: str  # admin, viewer, editor
    status: str  # active, inactive
    hashed_password: str
    extra: Optional[dict] = {}  # For dynamic fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# ✅ POST: Upload / Replace signatures
class UserSignature(BaseModel):
    name: str
    type: Literal["drawn", "pre_selected"]
    value: str
    isDefault: bool = False

class UpdateSignatureRequest(BaseModel):
    old_name: str
    new_name: Optional[str] = None
    isDefault: Optional[bool] = None

def generate_folder_id() -> str:
    return generate(size=10)
class FolderMapping(BaseModel):
    folderMappingId: str = Field(default_factory=generate_folder_id)
    path: str
class FolderAssignment(BaseModel):
    role_name: str
    assigned_folders: List[FolderMapping]


