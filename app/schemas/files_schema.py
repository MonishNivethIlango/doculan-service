from typing import List, Optional
from pydantic import BaseModel

class MoveFilesRequest(BaseModel):
    document_ids: Optional[List[str]] = []
    new_folder: str

