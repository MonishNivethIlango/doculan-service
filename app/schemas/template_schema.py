from pydantic import BaseModel, EmailStr
from typing import List, Optional

class Field(BaseModel):
    id: str
    type: str
    x: int
    y: int
    width: Optional[int]
    height: Optional[int]
    page: int
    color: str
    style: Optional[str]
    partyId: str
    required: Optional[bool] = False
    options: Optional[List[str]]

class Party(BaseModel):
    id: str
    name: str
    email: EmailStr
    color: str
    priority: Optional[int]

class TemplateCreate(BaseModel):
    template_name: str
    fields: List[Field]
    parties: Optional[List[Party]]
    document_id: str
    is_global: Optional[bool] = False

class TemplateLibrariesCreate(BaseModel):
    template_name: str
    fields: List[Field]
    parties: Optional[List[Party]]
    library_id: str

class TemplateUpdate(BaseModel):
    fields: Optional[List[Field]] = None
    parties: Optional[List[Party]] = None
    document_id: Optional[str] = None
    is_global: Optional[bool] = False


class TemplateLibrariesUpdate(BaseModel):
    fields: Optional[List[Field]] = None
    parties: Optional[List[Party]] = None
    library_id: Optional[str] = None


