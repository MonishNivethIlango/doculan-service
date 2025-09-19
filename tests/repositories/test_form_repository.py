from unittest.mock import patch, MagicMock
from repositories.form_repository import FormRepository

def test_create_form():
    with patch('repositories.form_repository.FormModel') as mock_model:
        mock_model.save_form.return_value = 'ok'
        result = FormRepository.create_form('f1', {'a': 1}, 'e')
        assert result == 'ok'
        mock_model.save_form.assert_called_with('f1', {'a': 1}, 'e')

def test_get_all_forms():
    with patch('repositories.form_repository.FormModel') as mock_model:
        mock_model.list_forms.return_value = ['f']
        result = FormRepository.get_all_forms('e')
        assert result == ['f']
        mock_model.list_forms.assert_called_with('e')

def test_read_form():
    with patch('repositories.form_repository.FormModel') as mock_model:
        mock_model.get_form.return_value = {'a': 1}
        result = FormRepository.read_form('f1', 'e')
        assert result == {'a': 1}
        mock_model.get_form.assert_called_with('f1', 'e')

def test_update_form():
    with patch('repositories.form_repository.FormModel') as mock_model:
        mock_model.update_form.return_value = 'ok'
        result = FormRepository.update_form('f1', {'a': 2}, 'e')
        assert result == 'ok'
        mock_model.update_form.assert_called_with('f1', {'a': 2}, 'e')

def test_delete_form():
    with patch('repositories.form_repository.FormModel') as mock_model:
        mock_model.delete_form.return_value = 'ok'
        result = FormRepository.delete_form('f1', 'e')
        assert result == 'ok'
        mock_model.delete_form.assert_called_with('f1', 'e')

def test_update_trackings():
    with patch('repositories.form_repository.FormModel') as mock_model:
        FormRepository.update_trackings('e', 'f1', {'x': 1})
        mock_model.update_form_track.assert_called_with('e', 'f1', {'x': 1})

def test_get_tracking():
    with patch('repositories.form_repository.FormModel') as mock_model:
        mock_model.get_form_track.return_value = 'track'
        result = FormRepository.get_tracking('e', 'f1')
        assert result == 'track'
        mock_model.get_form_track.assert_called_with('e', 'f1')

def test_validate_form():
    with patch('repositories.form_repository.FormModel') as mock_model:
        FormRepository.validate_form({'a': 1}, {'b': 2})
        mock_model.validate_form_values.assert_called_with({'a': 1}, {'b': 2})

def test_upload_pdf():
    with patch('repositories.form_repository.FormModel') as mock_model:
        mock_model.upload_pdfs.return_value = 'pdfkey'
        result = FormRepository.upload_pdf('e', 'f1', 'p', b'pdf', 'path', 'title', 'track')
        assert result == 'pdfkey'
        mock_model.upload_pdfs.assert_called_with('e', 'f1', 'p', b'pdf', 'path', 'title', 'track')

def test_get_pdf():
    with patch('repositories.form_repository.FormModel') as mock_model:
        mock_model.get_pdfs.return_value = b'pdf'
        result = FormRepository.get_pdf('e', 'f1', 'p', {'a': 1}, 'track')
        assert result == b'pdf'
        mock_model.get_pdfs.assert_called_with('e', 'f1', 'p', {'a': 1}, 'track')

def test_update_tracking_status():
    with patch('repositories.form_repository.FormModel') as mock_model:
        mock_model.update_tracking_status_by_party.return_value = 'ok'
        result = FormRepository.update_tracking_status('e', 'f1', 'p', 'status', 'req')
        assert result == 'ok'
        mock_model.update_tracking_status_by_party.assert_called_with('e', 'f1', 'p', 'status', 'req')
