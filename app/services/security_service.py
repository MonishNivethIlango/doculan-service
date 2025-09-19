from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from auth_app.app.database.connection import db
from utils.logger import logger


class EncryptionService:
    def __init__(self):
        self.collection = db["encryption"]

    async def resolve_encryption_email(self, email_domain: str) -> str:
        """Return encryption_email if exists, otherwise fallback to domain itself."""
        result = await self.collection.find_one(
            {"domain": email_domain},
            {"_id": 0, "encryption_email": 1}
        )
        return result["encryption_email"] if result else email_domain

class AESCipher:
    def __init__(self, email: str):

        self.key = (email + '0' * 16)[:16].encode()
        self.iv = (email + '0' * 16)[:16].encode()

    def encrypt(self, data: bytes) -> bytes:

        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        encrypted_data = cipher.encrypt(pad(data, AES.block_size))
        return encrypted_data

    def decrypt(self, encrypted_data: bytes) -> bytes:
        logger.info(f"decrypt-->{self.key}  decrypt-->{self.iv}")
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
        logger.info(f"decrypt-->{self.key}  decrypt-->{self.iv}")
        return decrypted_data

