import io
import mimetypes
from PIL import Image
from fpdf import FPDF
import pdfkit
from tempfile import NamedTemporaryFile

class AttachmentConverter:
    @staticmethod
    def convert_to_pdf_if_needed(file_bytes: bytes, filename: str) -> bytes:
        ext = filename.lower().split('.')[-1]

        if ext == "pdf":
            return file_bytes

        if ext == "docx":
            return AttachmentConverter._convert_docx_to_pdf(file_bytes)

        if ext in ["jpg", "jpeg", "png", "bmp"]:
            return AttachmentConverter._convert_image_to_pdf(file_bytes)

        if ext == "txt":
            return AttachmentConverter._convert_text_to_pdf(file_bytes.decode("utf-8"))

        raise ValueError(f"Unsupported file type for conversion: .{ext}")

    @staticmethod
    def _convert_docx_to_pdf(file_bytes: bytes) -> bytes:
        with NamedTemporaryFile(delete=False, suffix=".docx") as tmp_docx:
            tmp_docx.write(file_bytes)
            tmp_docx.flush()

            with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                pdfkit.from_file(tmp_docx.name, tmp_pdf.name)
                tmp_pdf.seek(0)
                return tmp_pdf.read()

    @staticmethod
    def _convert_image_to_pdf(image_bytes: bytes) -> bytes:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        output = io.BytesIO()
        image.save(output, format="PDF")
        output.seek(0)
        return output.read()

    @staticmethod
    def _convert_text_to_pdf(text: str) -> bytes:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)

        for line in text.splitlines():
            pdf.multi_cell(0, 10, line)

        output = io.BytesIO()
        pdf.output(output)
        output.seek(0)
        return output.read()
