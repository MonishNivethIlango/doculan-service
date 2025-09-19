from typing import List

from DataAccessLayer.storage.base import StorageStrategy
from app.services.security_service import AESCipher


class StorageManager:
    def __init__(self, strategy: StorageStrategy):
        self.strategy = strategy

    def upload(self, cipher: AESCipher, email: str, user_email: str, name: str, document_id: str, file, path_prefix: str = "",
                    overwrite: bool = False):
        # Pass path_prefix to the upload_file method of the strategy
        return self.strategy.upload_file(cipher, email, user_email, name, document_id, file, path_prefix,
                    overwrite)

    def get(self, cipher: AESCipher,email:str , document_id: str, return_pdf: bool = False):
        # Pass path_prefix to the get_file method of the strategy
        return self.strategy.get_file(cipher, email, document_id, return_pdf)

    def delete(self, email: str, document_id: str):
        # Pass path_prefix to the delete_file method of the strategy
        return self.strategy.delete_file(email, document_id)

    def update(self, email: str, document_id: str, new_file):
        # Pass path_prefix to the update_file method of the strategy
        return self.strategy.update_file(email, document_id, new_file)

    def list(self, email: str, folder_prefix: str = None):
        # Pass path_prefix to the list_files method of the strategy
        return self.strategy.list_files(email, folder_prefix)

    def move(self, email: str, document_ids: List[str], new_folder: str):
        # Pass path_prefix to the list_files method of the strategy
        return self.strategy.move_file(email, document_ids, new_folder)
