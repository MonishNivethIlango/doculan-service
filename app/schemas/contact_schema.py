from pydantic import BaseModel, EmailStr
from typing import Optional

class Address(BaseModel):
    street: str
    city: str
    state: str
    zip: str
    country: str

class Customer(BaseModel):
    name: str
    email: EmailStr
    organization: str
    mobile: str
    address: Address