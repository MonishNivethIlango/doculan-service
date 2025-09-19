# import boto3
# import os
# import logging
# from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
# from cryptography.hazmat.backends import default_backend
# from Crypto.Cipher import AES
# from Crypto.Util.Padding import pad, unpad
# from database.db_config import s3_client
#
# # ----------------------------
# # Logging Setup
# # ----------------------------
# LOG_DIR = "logs"
# os.makedirs(LOG_DIR, exist_ok=True)
# logging.basicConfig(
#     filename=os.path.join(LOG_DIR, "pdf_reencrypt.log"),
#     level=logging.INFO,
#     format="%(asctime)s - %(levelname)s - %(message)s"
# )
# console = logging.StreamHandler()
# console.setLevel(logging.INFO)
# formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
# console.setFormatter(formatter)
# logging.getLogger().addHandler(console)
#
# logger = logging.getLogger(__name__)
#
# # ----------------------------
# # AWS + Encryption Setup
# # ----------------------------
#
# BUCKET = "doculan-storage"
# PREFIX = "recruiter@virtualansoftware.com/"   # Folder inside bucket
#
# # Replace with your AES keys (must be 16/24/32 bytes)
# OLD_KEY = "recruiter@virtualansoftware.com"
# NEW_KEY = "elan.thangamani@virtualansoftware.com"
#
# # Toggle this to True for testing (no overwrite), False to actually re-encrypt
# DRY_RUN = False
#
#
# def encrypt(data: bytes, NEW_KEY) -> bytes:
#     key = (NEW_KEY + '0' * 16)[:16].encode()
#     iv = (NEW_KEY + '0' * 16)[:16].encode()
#     cipher = AES.new(key, AES.MODE_CBC, iv)
#     encrypted_data = cipher.encrypt(pad(data, AES.block_size))
#     return encrypted_data
#
#
# def decrypt(encrypted_data: bytes, OLD_KEY) -> bytes:
#     key = (OLD_KEY + '0' * 16)[:16].encode()
#     iv = (OLD_KEY + '0' * 16)[:16].encode()
#     cipher = AES.new(key, AES.MODE_CBC, iv)
#     decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
#     return decrypted_data
#
#
# def process_object(bucket: str, key: str):
#     try:
#         if DRY_RUN:
#             logger.info(f"[DRY RUN] Would process: {key}")
#             return
#
#         logger.info(f"Processing: {key}")
#
#         obj = s3_client.get_object(Bucket=bucket, Key=key)
#         encrypted_data = obj["Body"].read()
#
#         # 🔓 Decrypt with old key
#         decrypted = decrypt(encrypted_data, OLD_KEY)
#
#         # 🔐 Encrypt with new key
#         re_encrypted = encrypt(decrypted, NEW_KEY)
#
#         # Upload back to same location (same folder structure)
#         s3_client.put_object(Bucket=bucket, Key=key, Body=re_encrypted)
#
#         logger.info(f"✅ Success: {key}")
#     except Exception as e:
#         logger.error(f"❌ Failed: {key} | Error: {e}")
#
#
# def main():
#     paginator = s3_client.get_paginator("list_objects_v2")
#     for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
#         for obj in page.get("Contents", []):
#             key = obj["Key"]
#             if key.lower().endswith(".pdf"):
#                 process_object(BUCKET, key)
#
#
# if __name__ == "__main__":
#     main()
#

import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


def decrypt(encrypted_data: bytes, OLD_KEY: str) -> bytes:
    """Decrypts encrypted bytes using AES CBC with derived key/iv."""
    key = (OLD_KEY + '0' * 16)[:16].encode()
    iv = (OLD_KEY + '0' * 16)[:16].encode()
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
    return decrypted_data


def download_and_decrypt_pdf(file_path: str, old_key: str, output_path: str = None) -> str:
    """
    Reads an encrypted PDF from disk, decrypts it, and saves to output_path.

    :param file_path: Path to encrypted PDF file.
    :param old_key: Key string used for decryption.
    :param output_path: Optional path to save decrypted PDF. If None, saves next to input.
    :return: Path of decrypted PDF.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Encrypted file not found: {file_path}")

    # Read encrypted PDF
    with open(file_path, "rb") as f:
        encrypted_data = f.read()

    # Decrypt
    decrypted_data = decrypt(encrypted_data, old_key)

    # Prepare output path
    if output_path is None:
        base, ext = os.path.splitext(file_path)
        output_path = f"{base}_decrypted{ext}"

    # Save decrypted PDF
    with open(output_path, "wb") as f:
        f.write(decrypted_data)

    return output_path
decrypted_pdf_path = download_and_decrypt_pdf(
    file_path="C:/Users/vignesh.v_virtualans/Downloads/fw4 (1).pdf",
    old_key="elan.thangamani@virtualansoftware.com"
)
print(f"Decrypted PDF saved at: {decrypted_pdf_path}")
key = ("elan.thangamani@virtualansoftware.com" + '0' * 16)[:16].encode()
print(key)