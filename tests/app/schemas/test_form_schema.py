import pytest
from pydantic import ValidationError
from app.schemas.form_schema import (
    FileConfig, FormField, RegistrationForm, Party, EmailResponse,
    FormRequest, FormSubmissionRequest, OtpFormVerification, FormActionRequest, ResendFormRequest
)

def test_file_config():
    fc = FileConfig(acceptedTypes=['pdf'], maxSize=1000, multiple=True)
    assert fc.acceptedTypes == ['pdf']
    assert fc.maxSize == 1000
    assert fc.multiple is True

def test_form_field():
    fc = FileConfig(acceptedTypes=['pdf'], maxSize=1000, multiple=False)
    ff = FormField(id=1, type='text', label='Name', required=True, fileConfig=fc)
    assert ff.type == 'text'
    assert ff.fileConfig == fc

def test_registration_form():
    ff = FormField(id=1, type='text', label='Name', required=True)
    reg = RegistrationForm(formTitle='T', formDescription='D', formPath='P', fields=[ff])
    assert reg.formTitle == 'T'
    assert reg.fields[0].label == 'Name'

def test_party():
    p = Party(party_id='1', name='Alice', email='alice@example.com')
    assert p.email == 'alice@example.com'

def test_email_response():
    er = EmailResponse(email_subject='sub', email_body='body')
    assert er.email_subject == 'sub'
    assert er.email_body == 'body'

def test_form_request():
    p = Party(party_id='1', name='Bob', email='bob@example.com')
    er = EmailResponse(email_subject='s', email_body='b')
    req = FormRequest(
        form_id='f',
        validityDate='2025-01-01',
        remainder=1,
        parties=[p],
        email_responses=[er],
        holder=None,
        cc_emails=None,
        client_info={"ip": "1.1.1.1", "city": "C", "region": "R", "country": "X", "timezone": "UTC", "timestamp": "2025-01-01T00:00:00Z", "browser": "Chrome", "device": "PC", "os": "Windows"}
    )
    assert req.form_id == 'f'
    assert req.parties[0].name == 'Bob'

def test_form_submission_request():
    fsr = FormSubmissionRequest(
        form_id='f',
        form_tracking_id='t',
        values={'1': 'v'},
        party_email='test@example.com',
        client_info={"ip": "1.1.1.1", "city": "C", "region": "R", "country": "X", "timezone": "UTC", "timestamp": "2025-01-01T00:00:00Z", "browser": "Chrome", "device": "PC", "os": "Windows"}
    )
    assert fsr.values['1'] == 'v'

def test_otp_form_verification():
    otp = OtpFormVerification(
        form_tracking_id='t',
        form_id='f',
        party_id='p',
        otp='123',
        party_email='test@example.com',
        client_info={"ip": "1.1.1.1", "city": "C", "region": "R", "country": "X", "timezone": "UTC", "timestamp": "2025-01-01T00:00:00Z", "browser": "Chrome", "device": "PC", "os": "Windows"}
    )
    assert otp.otp == '123'

def test_form_action_request():
    far = FormActionRequest(form_id='f', form_tracking_id='t')
    # Only check attributes that exist in your model
    assert hasattr(far, "form_id")

def test_resend_form_request():
    rfr = ResendFormRequest(
        form_id='f',
        party_email='test@example.com',
        validityDate='2025-01-01',
        client_info={"ip": "1.1.1.1", "city": "C", "region": "R", "country": "X", "timezone": "UTC", "timestamp": "2025-01-01T00:00:00Z", "browser": "Chrome", "device": "PC", "os": "Windows"}
    )
    assert rfr.form_id == 'f'

