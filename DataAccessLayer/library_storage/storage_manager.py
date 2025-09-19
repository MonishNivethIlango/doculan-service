from typing import List

from DataAccessLayer.library_storage.base import StorageLibraryStrategy
from app.services.security_service import AESCipher


class LibraryStorageManager:
    def __init__(self, strategy: StorageLibraryStrategy):
        self.strategy = strategy

    def upload_library(self, cipher:AESCipher, email: str, library_id: str, file, path_prefix: str = "",
                    overwrite: bool = False, ):
        # Pass path_prefix to the upload_file method of the strategy
        return self.strategy.upload_library_file(cipher, email, library_id, file, path_prefix,
                    overwrite)

    def get_library(self, cipher:AESCipher, email:str , library_id: str, return_pdf: bool = False):
        # Pass path_prefix to the get_file method of the strategy
        return self.strategy.get_library_file(cipher, email, library_id, return_pdf)

    def delete_library(self, email: str, library_id: str):
        # Pass path_prefix to the delete_file method of the strategy
        return self.strategy.delete_library_file(email, library_id)

    def update_library(self, email: str, library_id: str, new_file):
        # Pass path_prefix to the update_file method of the strategy
        return self.strategy.update_library_file(email, library_id, new_file)

    def list_libraries(self):
        # Pass path_prefix to the list_files method of the strategy
        return self.strategy.list_library_file()

    def move_library(self, email: str, library_ids: List[str], new_folder: str):
        # Pass path_prefix to the list_files method of the strategy
        return self.strategy.move_library_file(email, library_ids, new_folder)
