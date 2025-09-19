from pydantic import BaseModel
from typing import Union
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date
from enum import Enum
from typing import Union
from pydantic import BaseModel

class CustomTypeEnum(str, Enum):
    pii = "PII"
    regular = "REGULAR"



class ColumnAddRequest(BaseModel):
    column_name: str
    default_value: Union[str, int, float, bool, None]
    custom_type: CustomTypeEnum
    type: str


class ColumnUpdateRequest(BaseModel):
    new_value: Union[str, int, float, bool, None]
