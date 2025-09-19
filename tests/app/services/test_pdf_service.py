import unittest
from unittest.mock import patch

import fitz

from app.services.pdf_service import PDFGenerator


class TestPDFGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = PDFGenerator()

    def extract_text_from_pdf(self, pdf_bytes):
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
            return text

    def test_generate_filled_pdf_normal_fields(self):
        form = {
            "formTitle": "Test Form",
            "fields": [
                {"label": "Name", "id": "1"},
                {"label": "Email", "id": "2"},
            ]
        }
        values = {
            "1": "Alice",
            "2": "alice@example.com"
        }

        result = self.generator.generate_filled_pdf(form, values)
        self.assertIsInstance(result, bytes)

        pdf_text = self.extract_text_from_pdf(result)
        self.assertIn("Name: Alice", pdf_text)
        self.assertIn("Email: alice@example.com", pdf_text)

    def test_generate_filled_pdf_normal_fields(self):
        form = {
            "formTitle": "Test Form",
            "fields": [
                {"label": "Name", "id": "1"},
                {"label": "Email", "id": "2"},
            ]
        }
        values = {
            "1": "Alice",
            "2": "alice@example.com"
        }

        result = self.generator.generate_filled_pdf(form, values)
        self.assertIsInstance(result, bytes)

        # Extract text from generated PDF
        with fitz.open(stream=result, filetype="pdf") as pdf:
            full_text = "\n".join(page.get_text() for page in pdf)

        self.assertIn("Name: Alice", full_text)
        self.assertIn("Email: alice@example.com", full_text)

    def test_generate_filled_pdf_returns_bytes(self):
        form = {
            "fields": [{"label": "X", "id": "1"}]
        }
        values = {"1": "Y"}

        pdf_bytes = self.generator.generate_filled_pdf(form, values)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 0)


if __name__ == '__main__':
    unittest.main()
