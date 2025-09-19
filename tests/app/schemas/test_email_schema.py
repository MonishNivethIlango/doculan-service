import pytest
from pydantic import ValidationError
from app.schemas.email_schema import EmailRequest, OTPVerifyRequest

def test_email_request_valid():
    req = EmailRequest(email='user@example.com')
    assert req.email == 'user@example.com'

def test_email_request_invalid():
    with pytest.raises(ValidationError):
        EmailRequest(email='not-an-email')

def test_otp_verify_request_valid():
    req = OTPVerifyRequest(email='user@example.com', otp='123456')
    assert req.email == 'user@example.com'
    assert req.otp == '123456'

def test_otp_verify_request_invalid_email():
    with pytest.raises(ValidationError):
        OTPVerifyRequest(email='bad', otp='123456')

def test_otp_verify_request_missing_otp():
    with pytest.raises(ValidationError):
        OTPVerifyRequest(email='user@example.com')
