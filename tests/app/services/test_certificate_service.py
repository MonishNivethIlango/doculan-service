import sys
import importlib
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def _isolate_certificate_service_module():
    # Fresh module each test to avoid stale references after suite-wide reloads
    sys.modules.pop('app.services.certificate_service', None)
    import app.services.certificate_service as cs  # noqa: F401
    importlib.reload(cs)
    yield


@patch("app.services.certificate_service.env")
@patch("app.services.certificate_service.HTML")
def test_render_form_pdf_success(mock_html, mock_env):
    from app.services import certificate_service
    mock_template = MagicMock()
    mock_template.render.return_value = "<html><body>Form</body></html>"
    mock_env.get_template.return_value = mock_template
    mock_html.return_value.write_pdf.return_value = b"formpdf"
    data = {"field": "value"}
    result = certificate_service.CertificateService.render_form_pdf(data, template_name="form.html")
    assert result == b"formpdf"
    mock_env.get_template.assert_called_once_with("form.html")
    mock_template.render.assert_called_once_with(**data)
    mock_html.return_value.write_pdf.assert_called_once()


@patch("app.services.certificate_service.env")
def test_render_form_pdf_template_not_found(mock_env):
    from app.services import certificate_service
    mock_env.get_template.side_effect = Exception("Form template not found")
    data = {"field": "value"}
    with pytest.raises(Exception) as exc:
        certificate_service.CertificateService.render_form_pdf(data, template_name="missing_form.html")
    assert "Form template not found" in str(exc.value)


@patch("app.services.certificate_service.env")
@patch("app.services.certificate_service.HTML")
def test_render_form_pdf_empty_data(mock_html, mock_env):
    from app.services import certificate_service
    mock_template = MagicMock()
    mock_template.render.return_value = "<html><body>Empty</body></html>"
    mock_env.get_template.return_value = mock_template
    mock_html.return_value.write_pdf.return_value = b"emptypdf"
    data = {}
    result = certificate_service.CertificateService.render_form_pdf(data, template_name="form.html")
    assert result == b"emptypdf"
    mock_env.get_template.assert_called_once_with("form.html")
    mock_template.render.assert_called_once_with(**data)
    mock_html.return_value.write_pdf.assert_called_once()


@patch("app.services.certificate_service.env")
@patch("app.services.certificate_service.HTML")
def test_render_form_pdf_render_error(mock_html, mock_env):
    from app.services import certificate_service
    mock_template = MagicMock()
    mock_template.render.side_effect = Exception("Render error")
    mock_env.get_template.return_value = mock_template
    data = {"field": "value"}
    with pytest.raises(Exception) as exc:
        certificate_service.CertificateService.render_form_pdf(data, template_name="form.html")
    assert "Render error" in str(exc.value)


@patch("app.services.certificate_service.env")
@patch("app.services.certificate_service.HTML")
def test_render_form_pdf_pdf_generation_error(mock_html, mock_env):
    from app.services import certificate_service
    mock_template = MagicMock()
    mock_template.render.return_value = "<html><body>Form</body></html>"
    mock_env.get_template.return_value = mock_template
    mock_html.return_value.write_pdf.side_effect = Exception("PDF error")
    data = {"field": "value"}
    with pytest.raises(Exception) as exc:
        certificate_service.CertificateService.render_form_pdf(data, template_name="form.html")
    assert "PDF error" in str(exc.value)