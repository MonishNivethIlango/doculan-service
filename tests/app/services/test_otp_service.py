import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException, status
from app.services.otp_service import OtpService
from app.schemas.form_schema import OtpFormVerification
from app.schemas.tracking_schemas import OTPVerification

@pytest.fixture
def otp_verification_data():
    return OTPVerification(
        party_id="p1",
        tracking_id="track1",
        document_id="doc1",
        otp="123456",
        client_info={
            "ip": "127.0.0.1",
            "city": "TestCity",
            "region": "TestRegion",
            "country": "TestCountry",
            "timezone": "UTC",
            "timestamp": "2025-08-13T00:00:00Z",
            "browser": "Chrome",
            "os": "Windows",
            "device": "Desktop"
        }
    )

@pytest.fixture
def otp_form_verification_data():
    return OtpFormVerification(
        form_id="form1",
        party_email="party@example.com",
        otp="654321",
        client_info={
            "ip": "127.0.0.1",
            "city": "TestCity",
            "region": "TestRegion",
            "country": "TestCountry",
            "timezone": "UTC",
            "timestamp": "2025-08-13T00:00:00Z",
            "browser": "Chrome",
            "os": "Windows",
            "device": "Desktop"
        }
    )

def test_send_otp_party_success():
    with patch("app.services.otp_service.generate_otp", return_value="123456"), \
         patch("app.services.otp_service.MetadataService.get_email_by_party_id", return_value={"email": "party@example.com"}), \
         patch("app.services.otp_service.EmailService.send_otp_verification_link") as mock_send:
        result = OtpService.send_otp_party("user@example.com", "p1", "track1", "doc1")
        assert result["message"] == "OTP sent successfully"
        mock_send.assert_called_once_with(recipient_email="party@example.com", otp="123456")

def test_send_otp_party_http_exception():
    with patch("app.services.otp_service.generate_otp", return_value="123456"), \
         patch("app.services.otp_service.MetadataService.get_email_by_party_id", side_effect=HTTPException(status_code=404, detail="not found")):
        with pytest.raises(HTTPException) as exc_info:
            OtpService.send_otp_party("user@example.com", "p1", "track1", "doc1")
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

def test_send_otp_party_unexpected_exception():
    with patch("app.services.otp_service.generate_otp", side_effect=Exception("fail")):
        with pytest.raises(HTTPException) as exc_info:
            OtpService.send_otp_party("user@example.com", "p1", "track1", "doc1")
        assert exc_info.value.status_code == 500
        assert "internal server error" in exc_info.value.detail.lower()

def test_verify_otp_for_party_success(otp_verification_data):
    with patch("app.services.otp_service.verify_otp", return_value=True), \
         patch("app.services.otp_service.DocumentTrackingManager.log_action") as mock_log:
        result = OtpService.verify_otp_for_party("user@example.com", otp_verification_data)
        assert result["status"] == "opened"
        mock_log.assert_called_once()

def test_verify_otp_for_party_invalid(otp_verification_data):
    data = OTPVerification(
        party_id="p1",
        tracking_id="track1",
        document_id="doc1",
        otp="wrong",
        client_info=otp_verification_data.client_info
    )
    with patch("app.services.otp_service.verify_otp", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            OtpService.verify_otp_for_party("user@example.com", data)
        assert exc_info.value.status_code == 500
        assert "Internal Server Error" in exc_info.value.detail

def test_verify_otp_for_party_exception(otp_verification_data):
    with patch("app.services.otp_service.verify_otp", side_effect=Exception("fail")):
        with pytest.raises(HTTPException) as exc_info:
            OtpService.verify_otp_for_party("user@example.com", otp_verification_data)
        assert exc_info.value.status_code == 500
        assert "Internal Server Error" in exc_info.value.detail

def test_send_form_otp_success():
    # Patch s3_client.get_object to return tracking data with party_email as key
    tracking_json = '{"party@example.com": {"status": "pending"}}'
    with patch("app.services.otp_service.generate_form_otp", return_value="654321"), \
         patch("app.services.otp_service.EmailService.send_otp_verification_link") as mock_send, \
         patch("app.services.otp_service.logger") as mock_logger, \
         patch("app.services.otp_service.s3_client.get_object", return_value={"Body": MagicMock(read=lambda: tracking_json.encode())}):
        result = OtpService.send_form_otp("form1", "party@example.com", email="user@example.com")
        assert result["message"] == "OTP sent successfully"
        assert result["party_email"] == "party@example.com"
        assert result["form_id"] == "form1"
        mock_send.assert_called_once_with("party@example.com", "654321")
        assert mock_logger.info.called

def test_send_form_otp_exception():
    from botocore.exceptions import ClientError
    error_response = {'Error': {'Code': 'NoSuchKey'}}
    with patch("app.services.otp_service.generate_form_otp", side_effect=Exception("fail")), \
         patch("app.services.otp_service.logger") as mock_logger, \
         patch("app.services.otp_service.s3_client.get_object", side_effect=ClientError(error_response, "GetObject")):
        with pytest.raises(HTTPException) as exc_info:
            OtpService.send_form_otp("form1", "party@example.com", email="user@example.com")
        assert exc_info.value.status_code == 404
        assert "Tracking data not found for this form" in exc_info.value.detail
        # logger.error is not called for 404, so do not assert it

def test_generate_otp_length():
    otp = OtpService.generate_otp(8)
    assert isinstance(otp, str)
    assert len(otp) == 8
    assert otp.isdigit()

def test_verify_form_otp_for_party_success(otp_form_verification_data):
    with patch("app.services.otp_service.verify_form_otp", return_value=True), \
         patch("app.services.otp_service.logger") as mock_logger:
        result = OtpService.verify_form_otp_for_party("user@example.com", otp_form_verification_data)
        assert result["status"] == "OTP Verified and opened status updated"
        assert result["party_email"] == "party@example.com"
        assert result["form_id"] == "form1"
        assert mock_logger.info.called

def test_verify_form_otp_for_party_invalid(otp_form_verification_data):
    with patch("app.services.otp_service.verify_form_otp", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            OtpService.verify_form_otp_for_party("user@example.com", otp_form_verification_data)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid OTP" in exc_info.value.detail

def test_verify_form_otp_for_party_exception(otp_form_verification_data):
    with patch("app.services.otp_service.verify_form_otp", side_effect=Exception("fail")), \
         patch("app.services.otp_service.logger") as mock_logger:
        with pytest.raises(HTTPException) as exc_info:
            OtpService.verify_form_otp_for_party("user@example.com", otp_form_verification_data)
        assert exc_info.value.status_code == 500
        assert "internal server error" in exc_info.value.detail.lower()
        assert mock_logger.error.called