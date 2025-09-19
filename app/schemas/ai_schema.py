from pydantic import BaseModel, EmailStr
from typing import Optional

class AiRequest(BaseModel):
    prompt: str
    type: str