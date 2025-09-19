import base64
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

import config

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT")

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def get_base64_logo(path: str) -> str:
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"


import base64
from io import BytesIO
from PyPDF2 import PdfReader


def count_pages_from_base64_pdf(base64_pdf: str) -> int:
    try:
        # Decode the base64 PDF (handle data URI format too)
        if base64_pdf.startswith("data:application/pdf;base64,"):
            base64_pdf = base64_pdf.split(",")[1]
        pdf_bytes = base64.b64decode(base64_pdf)

        # Read PDF from bytes
        reader = PdfReader(BytesIO(pdf_bytes))

        return len(reader.pages)
    except Exception as e:
        print(f"Failed to count pages: {e}")
        return 0


from datetime import datetime

def format_datetime(dt_str):
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%d %b %Y, %I:%M %p")  # e.g. 25 Jul 2025, 11:42 PM