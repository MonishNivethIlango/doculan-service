import io
import logging
import tempfile
import zipfile
from io import BytesIO
from datetime import datetime, timezone
from typing import Dict
import botocore
from botocore.exceptions import ClientError
from fastapi import HTTPException
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign.general import SigningError
from pyhanko_certvalidator import ValidationContext
from starlette.responses import StreamingResponse
from fpdf import FPDF

from pyhanko.sign.fields import SigFieldSpec, append_signature_field
from pyhanko.sign import signers, fields, PdfSigner, PdfSignatureMetadata
from pyhanko.sign.timestamps import HTTPTimeStamper, TimestampRequestError

from app.schemas.tracking_schemas import ClientInfo
from app.services.audit_service import document_tracking_manager
from app.services.certificate_service import certificate_service
from app.services.pdf_form_field_renderer_service import PDFFieldInserter
from app.services.security_service import AESCipher, EncryptionService
from config import config
from database.db_config import s3_client
from repositories.s3_repo import (
    get_signed,
    rendered_sign_s3,
    render_sign_update,
    load_document_metadata,
    store_tracking_metadata,s3_download_bytes, _list_objects, get_document_name
)
from utils.drive_client import get_base64_logo
from utils.security import format_user_datetime
from pyhanko.sign.timestamps import HTTPTimeStamper




logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def extract_email(s: str) -> str:
    if "/" in s:
        return s.split("/")[-1]
    return s

class PDFSigner:
    def __init__(self):
        self.timestamper = self._load_timestamper()

    def _load_timestamper(self) -> HTTPTimeStamper | None:
        """
        Initialize a TSA object with a fallback mechanism.
        Returns None if all TSA servers are unreachable.
        """
        tsa_urls = [
            "https://freetsa.org/tsr",
            "http://timestamp.sectigo.com",
            "http://timestamp.globalsign.com/scripts/timstamp.dll"
        ]

        for url in tsa_urls:
            try:
                tsa = HTTPTimeStamper(url, timeout=30)
                # Optional: test connectivity with a dry-run timestamp
                # tsa.async_request_tsa_response(b"dummy")  # Uncomment if async context available
                logger.info(f"[TSA] Initialized TSA: {url}")
                return tsa
            except TimestampRequestError as e:
                logger.warning(f"[TSA] Server unreachable: {url} ({e})")
            except Exception as e:
                logger.warning(f"[TSA] Failed to initialize TSA: {url} ({e})")

        logger.error("[TSA] No TSA servers reachable. Timestamps will be skipped.")
        return None

    async def sign_pdf_with_user_cert(self, email: str, signed_pdf: bytes, tracking_id: str) -> bytes:
        try:
            signer = signers.SimpleSigner.load_pkcs12(
                pfx_file=config.ESIGN_CERT,
                passphrase=config.CERT_PASSWORD.encode("utf-8")
            )
            if signer.signing_cert is None:
                raise ValueError("Signing certificate not found in PKCS#12 file.")

            logger.info(f"[Signing] Certificate loaded successfully for {email}")

            input_stream = io.BytesIO(signed_pdf)
            pdf_writer = IncrementalPdfFileWriter(input_stream)

            # append_signature_field(pdf_writer, SigFieldSpec(sig_field_name=f"TrackingId:{tracking_id}"))
            logger.info(f"[Signing] Signature field 'Tracking-Id:{tracking_id}' added for {email}")
            email = extract_email(email)

            signature_meta = PdfSignatureMetadata(
                field_name=f"Tracking-Id:{tracking_id}",
                reason="Verifiable digital PDF exported from www.doculan.ai",
                name=email,
                use_pades_lta=True
            )


            pdf_signer = PdfSigner(
                signature_meta=signature_meta,
                signer=signer,
                timestamper=self.timestamper
            )

            output_stream = BytesIO()
            await pdf_signer.async_sign_pdf(pdf_writer, output=output_stream)

            logger.info(f"[Signing] PDF signing complete with timestamp for {email}")
            return output_stream.getvalue()

        except SigningError as e:
            logger.error(f"[Signing] PyHanko signing error for {email}: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"[Signing] Failed to sign PDF for {email}: {e}", exc_info=True)
            raise

    async def render_signed_pdf(self, email, fields, document_id, tracking_id, pdf_size, party_id):
        try:
            logger.info(f"[Render] Rendering fields for {email} on document {document_id}")
            pdf_doc, file_name = await rendered_sign_s3(email, document_id)
            if pdf_doc is None:
                logger.error("[Render] Failed to load PDF document.")
                return None

            ui_pdf_width = pdf_size.get("pdfWidth", 595)
            ui_pdf_height = pdf_size.get("pdfHeight", 842)

            pdfFieldInserter = PDFFieldInserter()
            logger.info(fields)
            for field in fields:
                if not field.get("signed") or not field.get("value"):
                    continue
                page_number = field.get("page", 0)
                try:
                    self.sign_type(email, field, page_number, pdf_doc, ui_pdf_height, ui_pdf_width, tracking_id, party_id)
                except Exception as e:
                    logger.error(f"[Render] Error rendering field on page {page_number}: {e}")

            pdfFieldInserter.insert_tracking_id(pdf_doc, tracking_id)

            signed_bytes = pdf_doc.write()
            final_signed_pdf = await self.sign_pdf_with_user_cert(email, signed_bytes, tracking_id)

            # Save signed PDF to S3 or wherever required
            # render_sign_update(email, final_signed_pdf, tracking_id, document_id)

            logger.info("[Render] Document rendering and signing completed")
            pdf_base64 = await render_sign_update(email, final_signed_pdf, tracking_id, document_id)
            return pdf_base64, file_name

        except Exception as e:
            logger.error(f"[Render] Failed rendering/saving signed PDF: {e}", exc_info=True)
            return None


    def sign_type(self, email, field, page_number, pdf_doc, ui_pdf_height, ui_pdf_width, tracking_id, party_id):
        pdfFieldInserter = PDFFieldInserter()
        field_type, height, page, style, value, width, x, y = pdfFieldInserter.transform_field_coordinates(email=email,
            field=field, page_number=page_number, pdf_doc=pdf_doc, ui_pdf_height=ui_pdf_height, ui_pdf_width=ui_pdf_width
        )
        logger.info(f"transform_field_coordinates : {value}")
        pdfFieldInserter.insert_field_value_to_pdf(
            email=email, field=field, field_type=field_type, height=height, page=page, page_number=page_number, pdf_doc=pdf_doc, style=style, value=value, width=width, x=x, y=y, tracking_id=tracking_id, party_id=party_id
        )

    async def get_signed_file(self, email, tracking_id, document_id):
        try:
            return await self.get_signed_pdfs(email, tracking_id, document_id)
        except botocore.exceptions.ClientError:
            raise HTTPException(status_code=404, detail="Signed PDF not found")

    async def get_signed_pdfs(self, email: str, tracking_id: str, document_id: str):
        response = await get_signed(email, tracking_id, document_id)
        return StreamingResponse(BytesIO(response), media_type="application/pdf")

    async def finalize_party_signing_and_render_pdf(self, data, doc: ClientInfo, email, metadata, party_fields, party_status):
        logger.info(
            f"Finalizing signature for party_id={data.party_id}, tracking_id={data.tracking_id}, document_id={data.document_id}")

        if all(f.get("signed") for f in party_fields):
            current_time = datetime.now(timezone.utc).isoformat()

            context_data = {
                "ip": doc.ip,
                "browser": doc.browser,
                "os": doc.os,
                "location": {
                    "city": doc.city,
                    "region": doc.region,
                    "country": doc.country,
                    "timestamp": doc.timestamp,
                    "timezone": doc.timezone}
            }

            party_status["status"]["signed"] = {
                "isSigned": True,
                "dateTime": current_time,
                **context_data
            }

            logger.info(f"All fields signed for party_id={data.party_id}, marking as signed in metadata")
            await document_tracking_manager.log_action(email, data.document_id, data.tracking_id, "ALL_FIELDS_SIGNED", doc,
                                               data.party_id)

            try:
                logger.info(f"Rendering signed PDF for party_id={data.party_id}")
                signed_pdf_b64 = await self.render_signed_pdf(
                    email,
                    metadata["fields"],
                    data.document_id,
                    data.tracking_id,
                    metadata.get("pdfSize", {"pdfWidth": 595, "pdfHeight": 842}),data.party_id
                )
            except Exception as e:
                logger.exception(f"PDF rendering failed for party_id={data.party_id}")
                raise HTTPException(status_code=500, detail=f"Partial PDF rendering failed: {str(e)}")

            try:
                all_metadata = load_document_metadata(email, data.document_id)
                tracking = all_metadata.get("trackings", {}).get(data.tracking_id)

                if not tracking:
                    raise HTTPException(status_code=404, detail="Tracking ID not found in document metadata")

                all_signed = all(
                    party.get("status", {}).get("signed", {}).get("isSigned", False)
                    for party in tracking.get("parties", [])
                )

                if all_signed:
                    logger.info(f"All parties signed for tracking_id={data.tracking_id}, marking as completed")
                    tracking["tracking_status"] = {
                        "status": "completed",
                        "dateTime": current_time,
                        **context_data
                    }
                    store_tracking_metadata(email, data.document_id, data.tracking_id, tracking)

                return all_metadata

            except Exception as e:
                logger.exception(f"Failed to finalize completion for tracking_id={data.tracking_id}")
                return None
        else:
            logger.info(f"Not all fields signed yet for party_id={data.party_id}; skipping finalization")
            return None


class PDFGenerator:


    async def generate_filled_pdf(self, form: dict, values: Dict[str, str], email: str) -> bytes:
        # Build structured data for template
        form_certificate_data = {
            "title": form.get("formTitle", "Doculan - Digital Form"),
            "logo_path": get_base64_logo("./images/doculan-logo.png"),
            "fields": [
                {
                    "label": field.get("label", "Unknown Field"),
                    "type": field.get("type", "Unknown Field"),
                    "value": values.get(str(field.get("id"))) or values.get(field.get("label"), "")
                }
                for field in form.get("fields", [])
            ],
            "generated_at": await format_user_datetime(
                email, datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            ),
        }

        # Render using your wrapper
        return certificate_service.render_form_pdf(form_certificate_data, template_name="form.html")

    async def generate_pdf(self, email, form, submission):
        try:
            pdf_bytes = await self.generate_filled_pdf(form, submission.values, email)
            logger.debug("PDF generated successfully")
        except Exception as e:
            logger.error(f"PDF generation failed for form_id={submission.form_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="PDF generation failed")
        return pdf_bytes
    @staticmethod

    def decrypt_or_pass( cipher: AESCipher, data: bytes) -> bytes:
        try:
            return cipher.decrypt(data)
        except Exception:
            # Decryption failed — assume file is not encrypted and return as-is
            return data

    @staticmethod
    async def get_signed_package(email: str, tracking_id: str, document_id: str) -> StreamingResponse:
        pdfSigner = PDFSigner()
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)

        # 1. Get signed PDF
        document_name = get_document_name(email, document_id)
        document_name = document_name.replace(".pdf", "")

        signed_pdf_name = f"{document_name}_Authorized.pdf"
        signed_pdf_bytes = await get_signed(email, tracking_id, document_id)
        decrypted_signed_pdf = PDFGenerator.decrypt_or_pass(cipher, signed_pdf_bytes)

        # 2. List attachment files
        prefix = f"{email}/signed/{document_id}/{tracking_id}/"
        logger.info(prefix)

        attached_files = _list_objects(prefix)
        logger.info(attached_files)
        # 3. Try to fetch and decrypt certificate
        certificate_filename = f"certificate_{tracking_id}.pdf"
        certificate_key = f"{email}/certificates/documents/{document_id}/tracking/{tracking_id}.pdf"
        try:
            cert_response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=certificate_key)
            encrypted_certificate_bytes = cert_response['Body'].read()
            certificate_bytes = PDFGenerator.decrypt_or_pass(cipher, encrypted_certificate_bytes)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                certificate_bytes = None
            else:
                raise HTTPException(status_code=500, detail="Error retrieving certificate from S3")

        # 4. ZIP packaging
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add signed PDF
            zipf.writestr(signed_pdf_name, decrypted_signed_pdf)

            # Add attachments (decrypt or pass)
            for file_key in attached_files:
                file_name = file_key.split("/")[-1]
                if file_name == signed_pdf_name or file_name=="signed-pdf.pdf":
                    continue

                try:
                    encrypted_data = s3_download_bytes(file_key)
                    decrypted_data = PDFGenerator.decrypt_or_pass(cipher, encrypted_data)
                    zipf.writestr(file_name, decrypted_data)
                except Exception as ex:
                    raise HTTPException(status_code=500, detail=f"Error processing attachment: {file_name}") from ex

            # Add certificate
            if certificate_bytes:
                zipf.writestr(certificate_filename, certificate_bytes)

        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={document_name}_Executed_Files.zip"}
        )
