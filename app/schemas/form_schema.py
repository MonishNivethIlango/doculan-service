from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any, Literal

from app.schemas.tracking_schemas import Address


class FileConfig(BaseModel):
    acceptedTypes: List[str]
    maxSize: int
    multiple: bool

class FormField(BaseModel):
    id: int
    type: Literal['text', 'textarea', 'number', 'select', 'radio', 'checkbox', 'file', 'email', 'date', 'signature']
    label: str
    placeholder: Optional[str] = None
    required: bool
    sensitive: Optional[bool] = False
    options: Optional[List[str]] = None
    fileConfig: Optional[FileConfig] = None
    disclaimerText: Optional[str] = None

class RegistrationForm(BaseModel):
    formTitle: str
    formDescription: str
    formPath: str
    formLogo: Optional[str] = None
    fields: List[FormField]

class RegistrationLibraryForm(BaseModel):
    formTitle: str
    formDescription: str
    formPath: str
    formLogo: Optional[str] = None
    fields: List[FormField]
    tags: List[str]  # multiple tags allowed

class Party(BaseModel):
    party_id: str  # Unique party identifier
    name: str
    email: str  # party_email

class EmailResponse(BaseModel):
    email_subject: str
    email_body: str

class Holder(BaseModel):
    name: str
    email: str
    address: Optional[Address]

class ClientInfo(BaseModel):
    ip: str
    city: str
    region: str
    country: str
    timezone: str
    timestamp: str
    browser: str
    device: str
    os: str

class FormRequest(BaseModel):
    form_id: str
    validityDate: str
    remainder: int
    parties: List[Party]  # Parties identified by party_id and email
    email_responses: List[EmailResponse]
    holder: Optional[Holder]
    cc_emails: Optional[List[str]] = None  # Proper optional field
    client_info: ClientInfo


class FormSubmissionRequest(BaseModel):
    form_id: str
    party_email: str # Include party_email as well
    values: Dict[str, Any]
    client_info: ClientInfo

class OtpFormVerification(BaseModel):
    form_id: str
    party_email: str
    otp: str
    client_info: ClientInfo

class FormActionRequest(BaseModel):
    form_id: str
    party_email: Optional[EmailStr] = None

class ResendFormRequest(BaseModel):
    form_id: str
    party_email: EmailStr
    validityDate: Optional[str]
    client_info: ClientInfo


class OtpFormSend(BaseModel):
    form_id: str
    party_email: str

class FormCancelled(BaseModel):
    form_id: str
    party_email: str
    reason: str
    holder: Optional[Holder]
    client_info: ClientInfo

