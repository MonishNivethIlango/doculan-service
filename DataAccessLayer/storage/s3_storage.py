from io import BytesIO
from typing import List
from DataAccessLayer.storage.base import StorageStrategy

from config import config
from database.db_config import s3_client
from repositories.s3_repo import s3_update
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


class S3Storage(StorageStrategy):
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name

    from app.services.security_service import AESCipher

    def _get_metadata_key(self, email: str, document_id: str, path_prefix: str = "") -> str:
        return str(PurePosixPath(email, "metadata/data", f"{document_id}.json"))

    def _get_pdf_key(self, email: str, filename: str, path_prefix: str = "") -> str:
        return str(PurePosixPath(email, "files", path_prefix, filename))

    def _get_index_entry(self, email: str, document_id: str):
        index_key = f"{email}/index/document_index.json"
        try:
            response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            return data.get(document_id, {})
        except s3_client.exceptions.NoSuchKey:
            return {}
        except Exception as e:
            logger.warning(f"Failed to read index for document_id: {document_id}. Reason: {e}")
            return {}

    def upload_file(self, cipher:AESCipher, email: str, user_email: str, name: str, document_id: str, file: UploadFile, path_prefix: str = "",
                    overwrite: bool = False):
        try:
            if not file.filename:
                raise ValueError("Uploaded file must have a valid filename.")

            # Read file content
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            file_content = file.file.read()
            pdf_key = self._get_pdf_key(email, file.filename, path_prefix)
            metadata_key = self._get_metadata_key(email, document_id, path_prefix)

            logger.info(f"Uploading: {file.filename}, size: {file_size} bytes to {pdf_key}")

            # Check if file exists and overwrite not allowed
            try:
                s3_client.head_object(Bucket=self.bucket_name, Key=pdf_key)
                if not overwrite:
                    raise HTTPException(status_code=409, detail=f"File '{file.filename}' already exists.")
            except ClientError as e:
                if e.response['Error']['Code'] != "404":
                    logger.error("Unexpected S3 error during file existence check.")
                    raise

            # 1. Clean up any existing JSONs for same file_path but different document_id
            index_key = f"{email}/index/document_index.json"
            try:
                response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
                index_data = json.loads(response['Body'].read().decode('utf-8'))
            except s3_client.exceptions.NoSuchKey:
                index_data = {}
            except Exception as e:
                logger.warning("Failed to load document index. Reason: %s", e)
                index_data = {}

            # Track if any obsolete entries are removed
            to_delete = []
            for doc_id, entry in index_data.items():
                if entry.get("file_path") == pdf_key and doc_id != document_id:
                    old_meta = entry.get("metadata_path")
                    if old_meta:
                        try:
                            s3_client.delete_object(Bucket=self.bucket_name, Key=old_meta)
                            logger.info(f"Deleted stale metadata for old document_id: {doc_id} => {old_meta}")
                        except ClientError as ce:
                            logger.warning(f"Failed to delete old metadata: {old_meta}. Reason: {ce}")
                    to_delete.append(doc_id)

            # Remove obsolete document_ids from index
            for doc_id in to_delete:
                index_data.pop(doc_id)

            # 2. Delete old metadata for current document_id if path changed
            old_entry = index_data.get(document_id, {})
            old_metadata_path = old_entry.get("metadata_path")
            if overwrite and old_metadata_path and old_metadata_path != metadata_key:
                try:
                    s3_client.delete_object(Bucket=self.bucket_name, Key=old_metadata_path)
                    logger.info(f"Deleted outdated metadata for same document_id: {old_metadata_path}")
                except ClientError as ce:
                    if ce.response['Error']['Code'] != "NoSuchKey":
                        logger.warning(f"Failed to delete existing metadata: {old_metadata_path}. Reason: {ce}")

            # 3. Upload encrypted file
            from app.services.security_service import AESCipher
            encrypted_file = cipher.encrypt(file_content)
            from datetime import datetime, timezone
            last_modified = datetime.now(timezone.utc).isoformat()
            s3_client.put_object(
                Body=encrypted_file,
                Bucket=self.bucket_name,
                Key=pdf_key,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID,
                Metadata={
                "folder_created_by_name": name,
                "folder_created_by_email": user_email,
                "created_at": last_modified
            }
            )

            # 4. Upload metadata JSON
            metadata = {
                "document_id": document_id,
                "fileName": file.filename,
                "fileSizeBytes": file_size,
                "contentType": file.content_type,
                "last_modified": last_modified,
                "created_by": {"name":name, "email":user_email}
            }
            s3_client.put_object(
                Body=json.dumps(metadata),
                Bucket=self.bucket_name,
                Key=metadata_key,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )

            # 5. Update index with clean and final entry
            from datetime import datetime, timezone
            last_modified = datetime.now(timezone.utc).isoformat()

            index_data[document_id] = {
                "file_path": pdf_key,
                "metadata_path": metadata_key,
                "fileName": file.filename,
                "size": file_size,
                "last_modified": last_modified,
                "created_by": {"name":name, "email":user_email}
            }

            # Save index
            s3_client.put_object(
                Body=json.dumps(index_data),
                Bucket=self.bucket_name,
                Key=index_key,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )
            logger.info(f"Index updated at: {index_key}")

            return {
                "uploaded": True,
                "message": "File and metadata successfully uploaded",
                "document_id": document_id,
                "s3_keys": {"pdf": pdf_key, "metadata": metadata_key}
            }

        except ValueError as ve:
            logger.exception("Validation error.")
            raise ve
        except HTTPException:
            raise
        except ClientError as ce:
            logger.exception("S3 ClientError during file upload.")
            raise Exception(f"S3 ClientError: {str(ce)}")
        except Exception as e:
            logger.exception("Unexpected error during upload.")
            raise Exception(f"Unexpected error: {str(e)}")

    def _update_document_index(self, email: str, document_id: str, file_path: str, metadata_path: str, file_name: str):
        index_key = f"{email}/index/document_index.json"
        try:
            try:
                response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
                raw_data = response['Body'].read()
                try:
                    index_data = json.loads(raw_data.decode('utf-8'))
                except UnicodeDecodeError as ude:
                    logger.exception("Index file is not UTF-8 encoded or corrupted.")
                    raise Exception("The document index file is not in a valid UTF-8 JSON format.") from ude
                except json.JSONDecodeError as jde:
                    logger.exception("Index file is not valid JSON.")
                    raise Exception("The document index file content is not valid JSON.") from jde
            except s3_client.exceptions.NoSuchKey:
                index_data = {}
                logger.info(f"No existing index found, creating new one at: {index_key}")

            # Preserve existing entry values
            existing_entry = index_data.get(document_id, {})

            # Fetch file size and last_modified from S3 if file_path provided
            size = existing_entry.get("size")
            last_modified = existing_entry.get("last_modified")
            if file_path:
                try:
                    file_head = s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
                    size = file_head.get("ContentLength")
                    last_modified = file_head.get("LastModified").isoformat()
                except ClientError as ce:
                    logger.warning(f"Could not fetch head for file: {file_path}. S3 error: {ce}")

            updated_entry = {
                "file_path": file_path or existing_entry.get("file_path"),
                "metadata_path": metadata_path or existing_entry.get("metadata_path"),
                "fileName": file_name or existing_entry.get("fileName"),
                "size": size,
                "last_modified": last_modified
            }

            index_data[document_id] = updated_entry
            self._s3_update(index_data, index_key)

        except ClientError as ce:
            logger.exception("Failed to update S3 document index due to ClientError.")
            raise Exception(f"Failed to update document index: {str(ce)}")
        except Exception as e:
            logger.exception("Unexpected error while updating the document index.")
            raise Exception(f"Unexpected error while updating index: {str(e)}")

    def _s3_update(self, data: dict, key: str):
        s3_client.put_object(Body=json.dumps(data), Bucket=self.bucket_name, Key=key,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID)
        logger.info(f"S3 index updated at {key}")

    def get_file(self, cipher:AESCipher, email: str, document_id: str, return_pdf: bool = False):
        try:
            index_key = f"{email}/index/document_index.json"
            response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(response['Body'].read().decode('utf-8'))

            if document_id not in index_data:
                return {"error": "Document ID not found in index"}

            entry = index_data[document_id]
            file_path = entry.get("file_path")

            if not file_path:
                return {"error": "File path not available for document"}

            if return_pdf:
                try:
                    file_response = s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
                    encrypted_file_content = file_response["Body"].read()
                    decrypted_file_content = cipher.decrypt(encrypted_file_content)
                    return decrypted_file_content
                except Exception as e:
                    return {"error": f"Failed to retrieve PDF: {str(e)}"}

            return {"document_id": document_id, **entry}

        except s3_client.exceptions.NoSuchKey:
            return {"error": "Index file not found"}
        except ClientError as e:
            return {"error": str(e)}

    def list_files(self, email: str, folder_prefix: str = None):
        """
        Lists all files for the given email, optionally filtering by a specific folder.
        """
        index_key = f"{email}/index/document_index.json"

        try:
            index_obj = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(index_obj['Body'].read().decode('utf-8'))

            files = [
                {"document_id": doc_id, **details}
                for doc_id, details in index_data.items()
            ]

            if folder_prefix:
                files = [
                    f for f in files
                    if folder_prefix in f["file_path"]
                ]

            return {"files": files}

        except s3_client.exceptions.NoSuchKey:
            logger.warning(f"Index file not found: {index_key}")
            return {"files": []}
        except Exception as e:
            logger.exception(f"Error reading index file {index_key}: {e}")
            return {"files": []}

    def delete_file(self, email: str, document_id: str):
        try:
            index_key = f"{email}/index/document_index.json"
            response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(response['Body'].read().decode('utf-8'))

            if document_id not in index_data:
                return {"error": "Document ID not found in index"}

            file_path = index_data[document_id].get("file_path")
            metadata_path = index_data[document_id].get("metadata_path")

            def is_file_key(key: str) -> bool:
                return key and not key.endswith('/') and '.' in key.split('/')[-1]

            def ensure_folder_exists_after_deletion(deleted_key):
                folder_prefix = '/'.join(deleted_key.split('/')[:-1]) + '/'
                response = s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=folder_prefix)
                # response = list_s3_objects(folder_prefix)
                # Count remaining objects except the one being deleted
                remaining = [obj for obj in response.get('Contents', []) if obj['Key'] != deleted_key]
                if not remaining:
                    # Upload a placeholder file to retain the folder prefix
                    keep_key = folder_prefix + '.keep'
                    s3_client.put_object(Bucket=self.bucket_name, Key=keep_key, Body=b'',
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID)

            if file_path and is_file_key(file_path):
                s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
                ensure_folder_exists_after_deletion(file_path)

            if metadata_path and is_file_key(metadata_path):
                s3_client.delete_object(Bucket=self.bucket_name, Key=metadata_path)
                ensure_folder_exists_after_deletion(metadata_path)

            del index_data[document_id]
            s3_update(email, index_data)

            return {"message": "Document, metadata, and index entry deleted", "document_id": document_id}

        except s3_client.exceptions.NoSuchKey:
            return {"error": "Index file not found"}
        except ClientError as e:
            return {"error": str(e)}

    def update_file(self, email: str, document_id: str, new_file_b64: str, path_prefix: str = ""):
        try:
            index_key = f"{email}/index/document_index.json"
            response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(response['Body'].read().decode('utf-8'))

            if document_id in index_data:
                old_file_path = index_data[document_id].get("file_path")
                old_metadata_path = index_data[document_id].get("metadata_path")

                if old_file_path:
                    s3_client.delete_object(Bucket=self.bucket_name, Key=old_file_path)
                if old_metadata_path:
                    s3_client.delete_object(Bucket=self.bucket_name, Key=old_metadata_path)

                del index_data[document_id]
                s3_update(email, index_data)

        except s3_client.exceptions.NoSuchKey:
            pass
        except ClientError as e:
            return {"error": str(e)}

        decoded_bytes = base64.b64decode(new_file_b64)
        file_like = BytesIO(decoded_bytes)
        file_like.name = f"{document_id}.pdf"
        file_obj = UploadFile(file=file_like, filename=file_like.name)

        return self.upload_file(email, document_id, file_obj, path_prefix)

    def move_file(self, email: str, document_ids: List[str], new_folder: str):
        results = {}
        index_key = f"{email}/index/document_index.json"
        def is_file_key(key: str) -> bool:
            return key and not key.endswith('/') and '.' in key.split('/')[-1]

        def ensure_folder_exists_after_deletion(deleted_key):
            folder_prefix = '/'.join(deleted_key.split('/')[:-1]) + '/'
            # response = s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=folder_prefix)
            # response = list_s3_objects(folder_prefix)
            response = s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=folder_prefix)
            remaining = [obj for obj in response.get('Contents', []) if obj['Key'] != deleted_key]
            if not remaining:
                keep_key = folder_prefix + '.keep'
                s3_client.put_object(Bucket=self.bucket_name, Key=keep_key, Body=b'',
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID)
        try:
            response = s3_client.get_object(Bucket=self.bucket_name, Key=index_key)
            index_data = json.loads(response['Body'].read().decode('utf-8'))

            for document_id in document_ids:
                if document_id not in index_data:
                    results[document_id] = {"error": "Document ID not found in index"}
                    continue

                file_path = index_data[document_id].get("file_path")
                metadata_path = index_data[document_id].get("metadata_path")

                if not file_path or not metadata_path:
                    results[document_id] = {"error": "Missing file or metadata path"}
                    continue

                file_name = index_data[document_id].get("fileName")  # Fallback if not present
                new_file_path = f"{email}/files/{new_folder}/{file_name}"
                new_metadata_path = f"{email}/metadata/data/{document_id}.json"

                try:
                    # Copy files to new location
                    s3_client.copy_object(Bucket=self.bucket_name,
                                          CopySource={'Bucket': self.bucket_name, 'Key': file_path}, Key=new_file_path)
                    s3_client.copy_object(Bucket=self.bucket_name,
                                          CopySource={'Bucket': self.bucket_name, 'Key': metadata_path},
                                          Key=new_metadata_path)

                    # Delete original files
                    if is_file_key(file_path):
                        s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
                        ensure_folder_exists_after_deletion(file_path)


                    # Update index
                    index_data[document_id]["file_path"] = new_file_path
                    index_data[document_id]["metadata_path"] = new_metadata_path

                    results[document_id] = {"status": "moved"}

                except ClientError as e:
                    results[document_id] = {"error": str(e)}

            # Save updated index
            s3_update(email, index_data)
            return results

        except s3_client.exceptions.NoSuchKey:
            return {"error": "Index file not found"}
        except ClientError as e:
            return {"error": str(e)}
