import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends, Request
from app.schemas.contact_schema import Customer
from app.services.contact_service import ContactService
from auth_app.app.api.routes.deps import dynamic_permission_check, get_email_from_token
logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/contacts/", dependencies=[Depends(dynamic_permission_check)])
async def create_contact(contact: Customer, email: str = Depends(get_email_from_token)):
    contact_id = str(uuid.uuid4())
    ContactService.create_contact(contact_id, contact.dict(), email)
    return {"message": "Contact created successfully", "contact_id": contact_id}

@router.get("/contacts/{contact_id}", dependencies=[Depends(dynamic_permission_check)])
async def get_contact(contact_id: str, email: str = Depends(get_email_from_token)):
    contact_data = ContactService.get_contact(contact_id, email)
    if not contact_data:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact_data

@router.get("/contacts/", dependencies=[Depends(dynamic_permission_check)])
async def get_all_contacts(email: str = Depends(get_email_from_token)):
    contacts = ContactService.get_all_contacts(email)
    return {"contacts": contacts}

@router.put("/contacts/{contact_id}", dependencies=[Depends(dynamic_permission_check)])
async def update_contact(contact_id: str, contact: Customer, email: str = Depends(get_email_from_token)):
    if not ContactService.get_contact(contact_id, email):
        raise HTTPException(status_code=404, detail="Contact not found")
    ContactService.update_contact(contact_id, contact.dict(), email)
    return {"message": "Contact updated successfully"}

@router.delete("/contacts/{contact_id}", dependencies=[Depends(dynamic_permission_check)])
async def delete_contact(contact_id: str, email: str = Depends(get_email_from_token)):
    if not ContactService.get_contact(contact_id, email):
        raise HTTPException(status_code=404, detail="Contact not found")
    ContactService.delete_contact(contact_id, email)
    return {"message": "Contact deleted successfully"}