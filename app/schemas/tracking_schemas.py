from datetime import datetime
import json

from fastapi import Form
from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional, Dict, Literal

class Party(BaseModel):
    id: str
    name: str
    email: EmailStr
    color: str
    priority: Optional[int]

class Field(BaseModel):
    id: str                # Unique identifier for the field
    type: str              # Type of field, e.g., "signature", "text"
    x: int                 # X-coordinate (in pixels or units)
    y: int                 # Y-coordinate
    width: Optional[int]            # Width of the field
    height: Optional[int]            # Length (height) of the field
    page: int              # Page number in the document
    color: str
    style: Optional[str]
    partyId: str           # ID of the signer or user assigned
    required: Optional[bool] = False  # Whether the field is required
    options: Optional[List[str]]

class PdfSize(BaseModel):
    pdfWidth: int
    pdfHeight: int
class EmailResponse(BaseModel):
    email_subject: str
    email_body: str

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

class Address(BaseModel):
    address_line_1: str
    address_line_2: Optional[str]
    city: str
    country: Optional[str]
    state: str
    zipcode: str

class Holder(BaseModel):
    name: str
    email: str
    address: Optional[Address]
class DocumentRequest(BaseModel):
    document_id: str
    validityDate: str
    remainder: int
    pdfSize: PdfSize  # Corrected: keys are likely page numbers or identifiers
    parties: List["Party"]
    fields: List["Field"]
    email_response: List[EmailResponse]
    cc_emails: Optional[List[EmailStr]] = None  # Proper optional field
    client_info: ClientInfo
    holder: Optional[Holder]
    scheduled_datetime: Optional[datetime] = None  # ✅ correct type

    @field_validator("scheduled_datetime", mode="before")
    def empty_string_to_none(cls, v):
        if v == "" or v is None:
            return None
        return v

class PartyUpdateItem(BaseModel):
    party_id: str
    new_name: Optional[str] = None
    new_email: Optional[EmailStr] = None

class MultiPartyUpdateRequest(BaseModel):
    document_id: str
    tracking_id: str
    parties: List[PartyUpdateItem]



class DocumentResendRequest(BaseModel):
    document_id: str
    tracking_id: str
    validityDate: Optional[str]
    remainder: Optional[int]
    client_info: ClientInfo


class DocumentFieldRequest(BaseModel):
    document_id: str
    fields: List["Field"]

class OTPSend(BaseModel):
    tracking_id: str
    document_id: str
    party_id: str


class OTPVerification(BaseModel):
    tracking_id: str
    document_id: str
    party_id: str
    otp: str
    client_info: ClientInfo

class Fields(BaseModel):
    field_id: str
    font: Optional[str]
    style: Optional[str]
    value: Optional[str] = None

class UserFields(BaseModel):
    fields_ids: List[Fields]
class SignField(BaseModel):
    tracking_id: str
    document_id: str
    party_id: str
    fields: List[UserFields]
    client_info: ClientInfo

class FieldSubmission(BaseModel):
    id: str
    type: str
    x: float
    y: float
    page: int
    value: str
    font: Optional[str]


class SubmitFieldsRequest(BaseModel):
    document_id: str
    tracking_id: str
    party_id: str
    fields: List[FieldSubmission]

class SignatureStatusResponse(BaseModel):
    signatures: dict
    signed_pdf: str | None

class LogActionRequest(BaseModel):
    document_id: str
    tracking_id: str
    action: Literal["CANCELLED", "DECLINED"]
    party_id: Optional[str] = None
    reason: Optional[str] = None  # For DECLINED
    client_info: ClientInfo
    holder: Optional[Holder]

class Notification(BaseModel):
    id: str
    document_id: str
    tracking_id: str
    party_name: str
    party_email: str
    status: str
    message: str
    timestamp: str
    parties: List[Dict]  # List of party status objects
    read: bool