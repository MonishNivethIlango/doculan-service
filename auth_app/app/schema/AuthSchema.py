# app/schemas/auth_verify.py
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr


# Request model for login
class UserLogin(BaseModel):
    email: EmailStr
    password: Optional[str]

# Response model for token
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    is_temp_password: bool
    subscription_status: Optional[str] = None



class PreferencesUpdate(BaseModel):
    dateFormat: Optional[str]
    timeFormat: Optional[str]
    timezone: Optional[str]

class PreferencesOut(BaseModel):
    dateFormat: Optional[str] = None
    timeFormat: Optional[str] = None
    timezone: Optional[str] = None