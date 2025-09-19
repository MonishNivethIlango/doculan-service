import pytest
from unittest.mock import patch, MagicMock, call
from app.services.pdf_form_field_renderer_service import (
    PDFFieldInserter, generate_signature_b64_from_fontname, get_font_path_by_name
)
import base64
from PIL import Image
import io
import os

def test_get_font_path_by_name_known():
    assert get_font_path_by_name('dancingscript').endswith('DancingScript-Regular.ttf')
    assert get_font_path_by_name('marckscript').endswith('Marckscript-Regular.ttf')
    assert get_font_path_by_name('helvetica').endswith('Helvetica.ttf')

def test_get_font_path_by_name_unknown():
    assert get_font_path_by_name('unknownfont') is None

def test_generate_signature_b64_from_fontname_success(monkeypatch, tmp_path):
    font_path = tmp_path / 'TestFont.ttf'
    font_path.write_bytes(b'fakefont')
    monkeypatch.setattr('app.services.pdf_form_field_renderer_service.get_font_path_by_name', lambda n: str(font_path))
    monkeypatch.setattr('PIL.ImageFont.truetype', lambda path, size: MagicMock())
    monkeypatch.setattr('PIL.ImageDraw.Draw', lambda img: MagicMock(textbbox=lambda xy, text, font: (0,0,10,10), text=lambda xy, text, font, fill: None))
    monkeypatch.setattr('PIL.Image.new', lambda mode, size, color: MagicMock(save=lambda buf, format: buf.write(b'PNGDATA')))
    result = generate_signature_b64_from_fontname('sig', 'TestFont')
    assert result.startswith('data:image/png;base64,')

def test_generate_signature_b64_from_fontname_invalid_font(monkeypatch):
    monkeypatch.setattr('app.services.pdf_form_field_renderer_service.get_font_path_by_name', lambda n: None)
    with pytest.raises(ValueError):
        generate_signature_b64_from_fontname('sig', 'NoFont')

def test_load_fonts_from_directory(tmp_path):
    font_file = tmp_path / 'TestFont-Regular.ttf'
    font_file.write_bytes(b'fakefont')
    inserter = PDFFieldInserter(fonts_dir=str(tmp_path))
    assert 'Testfont' in inserter.font_name_to_file

def test_load_fonts_from_directory_missing():
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    assert inserter.font_name_to_file == {}

def test_get_valid_font_found(monkeypatch, tmp_path):
    font_file = tmp_path / 'TestFont-Regular.ttf'
    font_file.write_bytes(b'fakefont')
    inserter = PDFFieldInserter(fonts_dir=str(tmp_path))
    pdf_doc = MagicMock()
    monkeypatch.setattr(os.path, 'isfile', lambda p: True)
    monkeypatch.setattr(pdf_doc, 'insert_font', lambda name, fontfile: None)
    font = inserter.get_valid_font(pdf_doc, 'Testfont')
    assert font == 'Testfont'

def test_get_valid_font_not_found(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    pdf_doc = MagicMock()
    font = inserter.get_valid_font(pdf_doc, 'NoFont')
    assert font == 'helv'

def test_transform_field_coordinates():
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    pdf_doc = [MagicMock(rect=MagicMock(width=200, height=100))]
    field = {'x': 10, 'y': 20, 'width': 30, 'height': 40, 'type': 'text', 'style': 'drawn', 'value': 'abc'}
    result = inserter.transform_field_coordinates('email', field, 0, pdf_doc, 100, 200)
    assert result[0] == 'text'
    assert result[1] > 0

def test_insert_tracking_id(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    pdf_doc = [MagicMock(rect=MagicMock(width=100, height=100), insert_text=MagicMock())]
    monkeypatch.setattr('fitz.get_text_length', lambda text, fontname, fontsize: 10)
    inserter.get_valid_font = lambda doc, name: 'helv'
    inserter.insert_tracking_id(pdf_doc, 'trackid')
    pdf_doc[0].insert_text.assert_called()

def test_insert_wrapped_textarea_field(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    page = MagicMock(insert_text=MagicMock())
    pdf_doc = MagicMock()
    field = {'font': 'helv', 'font_size': 10}
    monkeypatch.setattr('fitz.get_text_length', lambda text, fontsize, fontname: 10)
    inserter.get_valid_font = lambda doc, name: 'helv'
    inserter.insert_wrapped_textarea_field(field, page, pdf_doc, 'hello world', 0, 0, 100, 20)
    page.insert_text.assert_called()

def test_insert_field_value_to_pdf_text(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    field = {'font': 'helv', 'font_size': 10, 'type': 'text'}
    page = MagicMock(insert_text=MagicMock())
    inserter.insert_text_field = MagicMock()
    inserter.insert_field_value_to_pdf('email', field, 'text', 10, page, 0, MagicMock(), 'drawn', 'val', 100, 1, 2, 'track', 'party')
    inserter.insert_text_field.assert_called()

def test_insert_field_value_to_pdf_signature_drawn(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    field = {'font': 'helv', 'font_size': 10, 'type': 'signature'}
    page = MagicMock()
    inserter.insert_transparent_signature = MagicMock()
    inserter.insert_flat_signature_image = MagicMock()
    with patch('app.services.pdf_form_field_renderer_service.s3_upload_bytes') as mock_s3_upload:
        img = Image.new('RGBA', (10, 10))
        b = io.BytesIO()
        img.save(b, format='PNG')
        b64 = base64.b64encode(b.getvalue()).decode('utf-8')
        value = f'data:image/png;base64,{b64}'
        with patch('PIL.Image.open', return_value=img):
            inserter.insert_field_value_to_pdf('email', field, 'signature', 10, page, 0, MagicMock(), 'drawn', value, 100, 1, 2, 'track', 'party')
        assert mock_s3_upload.called

def test_insert_field_value_to_pdf_signature_typed(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    field = {'font': 'helv', 'font_size': 10, 'type': 'signature'}
    page = MagicMock(insert_text=MagicMock())
    inserter.get_valid_font = lambda doc, name: 'helv'
    with patch('app.services.pdf_form_field_renderer_service.s3_upload_bytes') as mock_s3_upload:
        monkeypatch.setattr('app.services.pdf_form_field_renderer_service.generate_signature_b64_from_fontname', lambda **kwargs: 'data:image/png;base64,AAA')
        with patch('PIL.Image.open', return_value=Image.new('RGBA', (10, 10))):
            inserter.insert_field_value_to_pdf('email', field, 'signature', 10, page, 0, MagicMock(), 'typed', 'sig', 100, 1, 2, 'track', 'party')
        assert mock_s3_upload.called

def test_insert_field_value_to_pdf_checkbox(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    field = {'type': 'checkbox'}
    page = MagicMock(insert_image=MagicMock())
    img = Image.new('RGB', (10, 10))
    b = io.BytesIO()
    img.save(b, format='PNG')
    b64 = base64.b64encode(b.getvalue()).decode('utf-8')
    value = f'data:image/png;base64,{b64}'
    inserter.insert_field_value_to_pdf('email', field, 'checkbox', 10, page, 0, MagicMock(), 'drawn', value, 15, 1, 2, 'track', 'party')
    page.insert_image.assert_called()

def test_insert_field_value_to_pdf_date(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    field = {'type': 'date'}
    page = MagicMock(insert_text=MagicMock())
    inserter.insert_date_field = MagicMock()
    inserter.insert_field_value_to_pdf('email', field, 'date', 10, page, 0, MagicMock(), 'drawn', '2025-08-13', 100, 1, 2, 'track', 'party')
    inserter.insert_date_field.assert_called()

def test_insert_field_value_to_pdf_initial(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    field = {'type': 'initial'}
    page = MagicMock(insert_text=MagicMock())
    inserter.insert_typed_signature_text = MagicMock()
    inserter.insert_field_value_to_pdf('email', field, 'initial', 10, page, 0, MagicMock(), 'drawn', 'A', 100, 1, 2, 'track', 'party')
    inserter.insert_typed_signature_text.assert_called()

def test_insert_field_value_to_pdf_dropdown(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    field = {'type': 'dropdown'}
    page = MagicMock(insert_text=MagicMock())
    inserter.insert_typed_signature_text = MagicMock()
    inserter.insert_field_value_to_pdf('email', field, 'dropdown', 10, page, 0, MagicMock(), 'drawn', 'A', 100, 1, 2, 'track', 'party')
    inserter.insert_typed_signature_text.assert_called()

def test_insert_field_value_to_pdf_attach(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    field = {'type': 'attach'}
    page = MagicMock()
    inserter.insert_transparent_signature = MagicMock()
    inserter.insert_flat_signature_image = MagicMock()
    img = Image.new('RGBA', (10, 10))
    b = io.BytesIO()
    img.save(b, format='PNG')
    b64 = base64.b64encode(b.getvalue()).decode('utf-8')
    value = f'data:image/png;base64,{b64}'
    inserter.insert_field_value_to_pdf('email', field, 'attach', 10, page, 0, MagicMock(), 'drawn', value, 100, 1, 2, 'track', 'party')
    assert inserter.insert_transparent_signature.called or inserter.insert_flat_signature_image.called

def test_insert_text_field(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    page = MagicMock(insert_text=MagicMock())
    field = {'font': 'helv', 'font_size': 10}
    inserter.get_valid_font = lambda doc, name: 'helv'
    inserter.insert_text_field(field, page, MagicMock(), 'val', 1, 2)
    page.insert_text.assert_called()

def test_insert_typed_signature_text(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    page = MagicMock(insert_text=MagicMock())
    field = {'font': 'helv', 'font_size': 14}
    inserter.get_valid_font = lambda doc, name: 'helv'
    inserter.insert_typed_signature_text(field, page, 'sig', 1, 2)
    page.insert_text.assert_called()

def test_insert_date_field(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    page = MagicMock(insert_text=MagicMock())
    field = {'font': 'helv', 'font_size': 12}
    inserter.get_valid_font = lambda doc, name: 'helv'
    inserter.insert_date_field(field, page, MagicMock(), '2025-08-13', 1, 2)
    page.insert_text.assert_called()

def test_insert_checkbox_image(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    page = MagicMock(insert_image=MagicMock())
    monkeypatch.setattr('app.services.pdf_form_field_renderer_service.PDFFieldInserter.get_checkbox_base64', lambda self, val: base64.b64encode(b'img').decode('utf-8'))
    with patch('PIL.Image.open', return_value=Image.new('RGB', (10, 10))):
        inserter.insert_checkbox_image(True, 10, page, 10, 1, 2)
    page.insert_image.assert_called()

def test_insert_flat_signature_image(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    page = MagicMock(insert_image=MagicMock())
    img = Image.new('RGB', (10, 10))
    inserter.insert_flat_signature_image(10, img, page, 10, 1, 2)
    page.insert_image.assert_called()

def test_insert_transparent_signature(monkeypatch):
    inserter = PDFFieldInserter(fonts_dir='nonexistent_dir')
    page = MagicMock(insert_image=MagicMock())
    img = Image.new('RGBA', (10, 10))
    inserter.insert_transparent_signature(10, img, page, 10, 1, 2)
    page.insert_image.assert_called()
import base64
import pytest
import fitz  # PyMuPDF
from io import BytesIO
from PIL import Image
from unittest.mock import MagicMock, patch

from app.services.pdf_form_field_renderer_service import PDFFieldInserter


@pytest.fixture
def inserter():
    return PDFFieldInserter(fonts_dir="nonexistent_fonts")  # Avoid loading real fonts


@pytest.fixture
def dummy_pdf():
    # Create a blank in-memory PDF for testing
    pdf = fitz.open()
    pdf.new_page()
    return pdf


def test_transform_field_coordinates(inserter, dummy_pdf):
    field = {"x": 100, "y": 200, "width": 300, "height": 400}
    page_number = 0
    ui_width, ui_height = 600, 800
    # Add required keys for the function
    field["type"] = "text"
    field["style"] = "drawn"
    field["value"] = "abc"
    field_type, height, page, style, value, width, x, y = inserter.transform_field_coordinates(
        'email', field, page_number, dummy_pdf, ui_pdf_height=ui_height, ui_pdf_width=ui_width
    )
    assert field_type == 'text'
    assert width > 0 and height > 0
    assert isinstance(x, float)
    assert isinstance(y, float)


@patch.object(fitz.Page, "insert_text")
def test_insert_text_field(mock_insert_text, inserter, dummy_pdf):
    page = dummy_pdf[0]
    field = {
        "font": "helv",
        "font_size": 12
    }

    inserter.insert_text_field(field, page, dummy_pdf, "Test Text", 100, 150)
    mock_insert_text.assert_called_once()


@patch.object(fitz.Page, "insert_text")
def test_insert_typed_signature_text(mock_insert_text, inserter, dummy_pdf):
    page = dummy_pdf[0]
    field = {
        "font": "helv",
        "font_size": 14
    }

    inserter.insert_typed_signature_text(field, page, "MySignature", 50, 60)
    mock_insert_text.assert_called_once()


@patch.object(fitz.Page, "insert_text")
def test_insert_date_field(mock_insert_text, inserter, dummy_pdf):
    page = dummy_pdf[0]
    field = {
        "font": "helv",
        "font_size": 12
    }

    inserter.insert_date_field(field, page, dummy_pdf, "2025-07-18", 200, 250)
    mock_insert_text.assert_called_once()


@patch.object(fitz.Page, "insert_image")
def test_insert_flat_signature_image(mock_insert_image, inserter, dummy_pdf):
    image = Image.new("RGB", (100, 100), "white")
    page = dummy_pdf[0]
    inserter.insert_flat_signature_image(100, image, page, 100, 10, 20)
    mock_insert_image.assert_called_once()


@patch.object(fitz.Page, "insert_image")
def test_insert_transparent_signature(mock_insert_image, inserter, dummy_pdf):
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    page = dummy_pdf[0]
    inserter.insert_transparent_signature(100, image, page, 100, 10, 20)
    mock_insert_image.assert_called_once()
