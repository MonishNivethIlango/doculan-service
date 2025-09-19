import uuid
import logging
from io import BytesIO
from botocore.exceptions import ClientError
from pathlib import PurePosixPath
from starlette.responses import JSONResponse, StreamingResponse
from fastapi import HTTPException

from app.services.security_service import EncryptionService, AESCipher
from repositories.s3_repo import s3_head_upload

logger = logging.getLogger("doculan.files_service")


class FileService:
    def __init__(self, storage):
        self.storage = storage

    def generate_document_id(self):
        return str(uuid.uuid4())
    def _get_pdf_key(self, email: str, filename: str, path_prefix: str = "") -> str:
        return str(PurePosixPath(email, "files", path_prefix, filename))

    async def files_upload(self, email, user_email, name, files, path=None, overwrite=False):
        raw_path = (path or "").strip().strip("/")
        existing_files = []

        # ✅ Phase 1: Check if any file already exists
        for file in files:
            full_path = f"{raw_path}/{file.filename}" if raw_path else file.filename
            pdf_key = self._get_pdf_key(email, file.filename, raw_path)

            try:
                await s3_head_upload(pdf_key)
                if not overwrite:
                    existing_files.append(full_path)
            except ClientError as e:
                if e.response['Error']['Code'] != "404":
                    logger.error(f"S3 check error for {file.filename}: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Error checking '{file.filename}' in S3")

        if existing_files:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Upload rejected. One or more files already exist.",
                    "existing_files": existing_files
                }
            )

        # ✅ Phase 2: All files are safe, proceed with upload
        results = []
        for file in files:
            document_id = self.generate_document_id()
            full_path = f"{raw_path}/{file.filename}" if raw_path else file.filename
            try:
                encryption_service = EncryptionService()
                encryption_email = await encryption_service.resolve_encryption_email(email)
                cipher = AESCipher(encryption_email)
                result = self.storage.upload(cipher, email, user_email, name, document_id, file, raw_path, overwrite)
                results.append({
                    "document_id": document_id,
                    "filename": full_path,
                    "status": "uploaded"
                })
            except Exception as e:
                logger.error(f"Upload failed for {file.filename}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload {file.filename}: {str(e)}"
                )

        return results

    async def get_pdf(self, result, return_pdf: bool):
        try:
            if return_pdf:
                if isinstance(result, dict) and "error" in result:
                    return JSONResponse(content=result, status_code=400)
                return StreamingResponse(BytesIO(result), media_type="application/pdf")
            return JSONResponse(content=result)
        except Exception as e:
            logger.error("Failed to return PDF/JSON response: %s", e)
            return JSONResponse(content={"error": str(e)}, status_code=500)
