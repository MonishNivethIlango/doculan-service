import io
import pytest
from unittest.mock import patch, MagicMock
from app.services.pdf_converter import AttachmentConverter
from PIL import Image
import builtins

class DummyPDF:
    def __init__(self):
        self.pages = []
        self.font = None
    def add_page(self):
        self.pages.append('page')
    def set_auto_page_break(self, auto, margin):
        pass
    def set_font(self, font, size):
        self.font = (font, size)
    def multi_cell(self, w, h, txt):
        pass
    def output(self, output):
        output.write(b'PDFDATA')


def test_convert_pdf_returns_same_bytes():
    data = b'%PDF-1.4...'
    result = AttachmentConverter.convert_to_pdf_if_needed(data, 'file.pdf')
    assert result == data

def test_convert_docx_to_pdf_success(monkeypatch):
    fake_pdf = b'PDFDATA'
    def fake_from_file(docx, pdf):
        # Simulate writing to the PDF file
        with open(pdf, 'wb') as f:
            f.write(fake_pdf)
    monkeypatch.setattr('pdfkit.from_file', fake_from_file)
    # Patch open so that when the code tries to read the PDF file, it returns fake_pdf
    def fake_open(file, mode='rb', *args, **kwargs):
        # Only patch reading the PDF file
        if file.endswith('.pdf') and 'r' in mode:
            mock_file = MagicMock()
            mock_file.read.return_value = fake_pdf
            mock_file.__enter__.return_value = mock_file
            return mock_file
        return open_orig(file, mode, *args, **kwargs)
    open_orig = open
    with patch('builtins.open', side_effect=fake_open):
        docx_bytes = b'docxdata'
        result = AttachmentConverter._convert_docx_to_pdf(docx_bytes)
        assert result == fake_pdf

def test_convert_image_to_pdf_success(monkeypatch):
    img = Image.new('RGB', (10, 10), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    image_bytes = buf.read()
    monkeypatch.setattr('PIL.Image.open', lambda b: img)
    monkeypatch.setattr(img, 'convert', lambda mode: img)
    monkeypatch.setattr(img, 'save', lambda out, format: out.write(b'PDFDATA'))
    result = AttachmentConverter._convert_image_to_pdf(image_bytes)
    assert result == b'PDFDATA'

def test_convert_text_to_pdf_success(monkeypatch):
    monkeypatch.setattr('app.services.pdf_converter.FPDF', DummyPDF)
    text = 'Hello\nWorld'
    result = AttachmentConverter._convert_text_to_pdf(text)
    assert result == b'PDFDATA'

def test_convert_to_pdf_if_needed_pdf():
    data = b'%PDF-1.4...'
    result = AttachmentConverter.convert_to_pdf_if_needed(data, 'file.pdf')
    assert result == data

def test_convert_to_pdf_if_needed_docx(monkeypatch):
    monkeypatch.setattr(AttachmentConverter, '_convert_docx_to_pdf', lambda b: b'PDFDATA')
    result = AttachmentConverter.convert_to_pdf_if_needed(b'docxdata', 'file.docx')
    assert result == b'PDFDATA'

def test_convert_to_pdf_if_needed_image(monkeypatch):
    monkeypatch.setattr(AttachmentConverter, '_convert_image_to_pdf', lambda b: b'PDFDATA')
    for ext in ['jpg', 'jpeg', 'png', 'bmp']:
        result = AttachmentConverter.convert_to_pdf_if_needed(b'imagedata', f'file.{ext}')
        assert result == b'PDFDATA'

def test_convert_to_pdf_if_needed_txt(monkeypatch):
    monkeypatch.setattr(AttachmentConverter, '_convert_text_to_pdf', lambda t: b'PDFDATA')
    result = AttachmentConverter.convert_to_pdf_if_needed(b'hello', 'file.txt')
    assert result == b'PDFDATA'

def test_convert_to_pdf_if_needed_unsupported():
    with pytest.raises(ValueError) as exc:
        AttachmentConverter.convert_to_pdf_if_needed(b'data', 'file.exe')
    assert 'Unsupported file type' in str(exc.value)
