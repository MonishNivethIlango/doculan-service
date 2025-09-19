from typing import Optional, List
from pydantic import BaseModel


class MoveLibrariesRequest(BaseModel):
    library_ids: Optional[List[str]] = []
    new_folder: str
