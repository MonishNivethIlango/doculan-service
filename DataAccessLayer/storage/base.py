from abc import ABC, abstractmethod
from typing import List



class StorageStrategy(ABC):
    @abstractmethod
    def upload_file(self,cipher,  email: str, user_email: str, name: str, document_id: str, new_file, path_prefix: str = "",
                    overwrite: bool = False): pass

    @abstractmethod
    def get_file(self,cipher, email:str, document_id: str, return_pdf: bool = False): pass

    @abstractmethod
    def delete_file(self, email: str, document_id: str): pass

    @abstractmethod
    def update_file(self,email: str, document_id: str, new_file): pass

    @abstractmethod
    def list_files(self, email: str, folder_prefix: str = None): pass

    @abstractmethod
    def move_file(self, email: str, document_ids: List[str], new_folder: str): pass
