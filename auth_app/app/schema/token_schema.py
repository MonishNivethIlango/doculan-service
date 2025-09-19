from pydantic import BaseModel, EmailStr

class UserTokenData(BaseModel):
    id: str
    email: EmailStr
    role: str
