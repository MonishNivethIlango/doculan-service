from abc import ABC, abstractmethod
from typing import List

from app.services.security_service import AESCipher


class StorageLibraryStrategy(ABC):
    @abstractmethod
    def upload_library_file(self, cipher:AESCipher, email: str, library_id: str, new_file, path_prefix: str = "",
                    overwrite: bool = False): pass

    @abstractmethod
    def get_library_file(self,cipher:AESCipher, email:str, library_id: str, return_pdf: bool = False): pass

    @abstractmethod
    def delete_library_file(self, email: str, library_id: str): pass

    @abstractmethod
    def update_library_file(self,email: str, library_id: str, new_file): pass

    @abstractmethod
    def list_library_file(self): pass

    @abstractmethod
    def move_library_file(self, email: str, library_ids: List[str], new_folder: str): pass
