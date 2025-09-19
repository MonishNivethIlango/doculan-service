from typing import List

from DataAccessLayer.library_storage.base import StorageLibraryStrategy
from app.services.security_service import AESCipher
from config import config
from database.db_config import s3_client
from repositories.s3_repo import s3_update_libraries
from utils.timezones import TimeZoneUtils
import base64
import json
import logging
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
format = TimeZoneUtils()


class S3LibraryStorage(StorageLibraryStrategy):
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name

    # ------------------- Helpers -------------------

    def _get_metadata_key(self, email: str, library_id: str, path_prefix: str = "") -> str:
        return str(PurePosixPath("libraries/metadata/libraries", f"{library_id}.json"))

    def _get_pdf_key(self, email: str, filename: str, path_prefix: str = "") -> str:
        return str(PurePosixPath( "libraries", path_prefix, filename))

    def _get_index_entry(self, email: str, library_id: str):
        index_key = f"libraries/index/library_index.json"
        try:
            response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            return data.get(library_id, {})
        except s3_client.exceptions.NoSuchKey:
            return {}
        except Exception as e:
            logger.warning(f"Failed to read index for library_id: {library_id}. Reason: {e}")
            return {}

    # ------------------- Upload -------------------

    def upload_library_file(self, cipher:AESCipher, email: str, library_id: str, file: UploadFile, path_prefix: str = "",
                       overwrite: bool = False):
        try:
            if not file.filename:
                raise ValueError("Uploaded file must have a valid filename.")

            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
            file_content = file.file.read()

            pdf_key = self._get_pdf_key(email, file.filename, path_prefix)
            metadata_key = self._get_metadata_key(email, library_id, path_prefix)

            logger.info(f"Uploading library: {file.filename}, size: {file_size} bytes to {pdf_key}")

            # Prevent overwrite if not allowed
            try:
                s3_client.head_object(Bucket=self.bucket_name, Key=pdf_key)
                if not overwrite:
                    raise HTTPException(status_code=409, detail=f"Library '{file.filename}' already exists.")
            except ClientError as e:
                if e.response['Error']['Code'] != "404":
                    raise

            # Load index
            index_key = f"libraries/index/library_index.json"
            try:
                response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
                index_data = json.loads(response['Body'].read().decode('utf-8'))
            except s3_client.exceptions.NoSuchKey:
                index_data = {}
            except Exception:
                index_data = {}

            # Remove obsolete entries pointing to same file
            to_delete = []
            for lib_id, entry in index_data.items():
                if entry.get("file_path") == pdf_key and lib_id != library_id:
                    old_meta = entry.get("metadata_path")
                    if old_meta:
                        try:
                            s3_client.delete_object(Bucket=self.bucket_name, Key=old_meta)
                        except ClientError:
                            pass
                    to_delete.append(lib_id)
            for lib_id in to_delete:
                index_data.pop(lib_id)

            # Encrypt and upload PDF

            encrypted_file = cipher.encrypt(file_content)
            s3_client.put_object(
                Body=encrypted_file,
                Bucket=self.bucket_name,
                Key=pdf_key,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )

            # Metadata
            metadata = {
                "library_id": library_id,
                "fileName": file.filename,
                "fileSizeBytes": file_size,
                "contentType": file.content_type
            }
            s3_client.put_object(
                Body=json.dumps(metadata),
                Bucket=self.bucket_name,
                Key=metadata_key,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )

            # Update index
            from datetime import datetime, timezone
            last_modified = datetime.now(timezone.utc).isoformat()

            index_data[library_id] = {
                "file_path": pdf_key,
                "metadata_path": metadata_key,
                "fileName": file.filename,
                "size": file_size,
                "last_modified": last_modified
            }

            s3_client.put_object(
                Body=json.dumps(index_data),
                Bucket=self.bucket_name,
                Key=index_key,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )

            return {
                "uploaded": True,
                "message": "Library and metadata uploaded",
                "library_id": library_id,
                "s3_keys": {"pdf": pdf_key, "metadata": metadata_key}
            }

        except Exception as e:
            logger.exception("Unexpected error during library upload.")
            raise

    # ------------------- Get -------------------

    def get_library_file(self, cipher:AESCipher, email: str, library_id: str, return_pdf: bool = False):
        index_key = f"libraries/index/library_index.json"
        try:
            response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(response['Body'].read().decode('utf-8'))
            if library_id not in index_data:
                return {"error": "Library ID not found"}
            entry = index_data[library_id]
            file_path = entry.get("file_path")
            if return_pdf:
                file_resp = s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
                return cipher.decrypt(file_resp["Body"].read())
            return {"library_id": library_id, **entry}
        except s3_client.exceptions.NoSuchKey:
            return {"error": "Library index not found"}

    # ------------------- List -------------------

    def list_library_file(self):
        index_key = f"libraries/index/library_index.json"
        try:
            resp = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(resp['Body'].read().decode('utf-8'))
            return {"libraries": [{"library_id": lid, **d} for lid, d in index_data.items()]}
        except s3_client.exceptions.NoSuchKey:
            return {"libraries": []}

    # ------------------- Delete -------------------

    def delete_library_file(self, email: str, library_id: str):
        index_key = f"libraries/index/library_index.json"
        try:
            resp = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(resp['Body'].read().decode('utf-8'))
            if library_id not in index_data:
                return {"error": "Library not found"}
            file_path = index_data[library_id].get("file_path")
            metadata_path = index_data[library_id].get("metadata_path")
            if file_path:
                s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            if metadata_path:
                s3_client.delete_object(Bucket=self.bucket_name, Key=metadata_path)
            del index_data[library_id]
            s3_update_libraries(email, index_data, index_key="libraries/index/library_index.json")
            return {"message": "Library deleted", "library_id": library_id}
        except s3_client.exceptions.NoSuchKey:
            return {"error": "Library index not found"}

    # ------------------- Update -------------------

    def update_library_file(self, email: str, library_id: str, new_file: UploadFile, overwrite: bool = True):
        index_key = f"libraries/index/library_index.json"
        try:
            # Load index
            resp = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(resp['Body'].read().decode('utf-8'))

            if library_id not in index_data:
                return {"error": "Library not found"}

            # Delete old file + metadata
            old_entry = index_data[library_id]
            if old_entry.get("file_path"):
                s3_client.delete_object(Bucket=self.bucket_name, Key=old_entry["file_path"])
            if old_entry.get("metadata_path"):
                s3_client.delete_object(Bucket=self.bucket_name, Key=old_entry["metadata_path"])

            # Re-upload with same library_id
            return self.upload_library_file(email, library_id, new_file, overwrite=overwrite)

        except s3_client.exceptions.NoSuchKey:
            return {"error": "Library index not found"}
        except Exception as e:
            logger.exception("Error updating library")
            raise
        
    
    # ------------------- Move -------------------

    def move_library_file(self, email: str, library_id: List[str], new_folder: str):
        index_key = f"libraries/index/library_index.json"
        try:
            # Load index
            resp = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(resp['Body'].read().decode('utf-8'))

            if library_id not in index_data:
                return {"error": "Library not found"}

            entry = index_data[library_id]
            old_file_path = entry.get("file_path")
            old_metadata_path = entry.get("metadata_path")

            if not old_file_path or not old_metadata_path:
                return {"error": "Invalid library entry"}

            # Compute new S3 keys
            filename = entry["fileName"]
            new_file_key = str(PurePosixPath("libraries", new_folder, filename))
            new_metadata_key = str(PurePosixPath("libraries/metadata/libraries", f"{library_id}.json"))

            # Copy objects to new location
            s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={"Bucket": self.bucket_name, "Key": old_file_path},
                Key=new_file_key,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )
            s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={"Bucket": self.bucket_name, "Key": old_metadata_path},
                Key=new_metadata_key,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )

            # Delete old objects
            s3_client.delete_object(Bucket=self.bucket_name, Key=old_file_path)
            s3_client.delete_object(Bucket=self.bucket_name, Key=old_metadata_path)

            # Update index entry
            entry["file_path"] = new_file_key
            entry["metadata_path"] = new_metadata_key
            index_data[library_id] = entry

            s3_update_libraries(email, index_data, index_key="libraries/index/library_index.json")

            return {"message": "Library moved", "library_id": library_id, "new_path": new_file_key}

        except s3_client.exceptions.NoSuchKey:
            return {"error": "Library index not found"}
        except Exception as e:
            logger.exception("Error moving library")
            raise


