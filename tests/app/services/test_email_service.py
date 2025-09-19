import sys
from unittest.mock import MagicMock

# Patch the DB connection and any side-effectful imports before importing the app code
sys.modules['auth_app.app.database.connection'] = MagicMock(
    db=MagicMock(),
    save_document_url=MagicMock(),
    tracker_collection=MagicMock()
)

from unittest.mock import patch, MagicMock, AsyncMock
from app.services.email_service import EmailService
from app.schemas.form_schema import EmailResponse
from datetime import datetime
import unittest

class TestEmailServiceUnit(unittest.TestCase):
    def setUp(self):
        self.email_service = EmailService()
        self.email_service.sender = "from@example.com"
        self.email_service.username = "user"
        self.email_service.password = "pass"
        self.email_service.mail_server = "smtp.example.com"
        self.email_service.mail_port = 587
        self.test_email = "test@example.com"
        self.test_pdf_bytes = b"%PDF-1.4 test"
        self.test_subject = "Test Subject"
        self.test_body = "This is a test email."
        self.email_response = [EmailResponse(email_subject="Subject", email_body="Click [Document Link] please.")]
        self.single_email_response = EmailResponse(email_subject="Subject", email_body="Please use [Form Link]")


class TestEmailServiceUnit(unittest.TestCase):
    def setUp(self):
        self.email_service = EmailService()
        self.test_email = "test@example.com"
        self.test_pdf_bytes = b"%PDF-1.4 test"
        self.test_subject = "Test Subject"
        self.test_body = "This is a test email."
        self.email_response = [EmailResponse(email_subject="Subject", email_body="Click [Document Link] please.")]
        self.single_email_response = EmailResponse(email_subject="Subject", email_body="Please use [Form Link]")

    @patch("smtplib.SMTP")
    def test_send_email_plain_success(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        mock_server.sendmail.return_value = {}
        self.email_service.sender = "from@example.com"
        self.email_service.username = "user"
        self.email_service.password = "pass"
        self.email_service.mail_server = "smtp.example.com"
        self.email_service.mail_port = 587
        self.email_service.send_email(
            reply_name="Test Sender",
            reply_email="reply@example.com",
            recipient_email=self.test_email,
            subject=self.test_subject,
            body=self.test_body,
            is_html=False
        )
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.sendmail.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_email_with_attachment_success(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        mock_server.sendmail.return_value = {}
        self.email_service.sender = "from@example.com"
        self.email_service.username = "user"
        self.email_service.password = "pass"
        self.email_service.mail_server = "smtp.example.com"
        self.email_service.mail_port = 587
        self.email_service.send_email(
            reply_name="Test Sender",
            reply_email="reply@example.com",
            recipient_email=self.test_email,
            subject=self.test_subject,
            body=self.test_body,
            attachment_bytes=self.test_pdf_bytes,
            attachment_filename="test.pdf",
            is_html=True
        )
        mock_server.sendmail.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_email_with_inline_images(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        mock_server.sendmail.return_value = {}
        self.email_service.sender = "from@example.com"
        self.email_service.username = "user"
        self.email_service.password = "pass"
        self.email_service.mail_server = "smtp.example.com"
        self.email_service.mail_port = 587
        # base64 image
        inline_images = {"logo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"}
        self.email_service.send_email(
            reply_name="Test Sender",
            reply_email="reply@example.com",
            recipient_email=self.test_email,
            subject=self.test_subject,
            body=self.test_body,
            is_html=True,
            inline_images=inline_images
        )
        mock_server.sendmail.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_email_failure_raises(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        mock_server.sendmail.return_value = {"fail": "fail"}
        self.email_service.sender = "from@example.com"
        self.email_service.username = "user"
        self.email_service.password = "pass"
        self.email_service.mail_server = "smtp.example.com"
        self.email_service.mail_port = 587
        with self.assertRaises(RuntimeError):
            self.email_service.send_email(
                reply_name="Test Sender",
                reply_email="reply@example.com",
                recipient_email=self.test_email,
                subject=self.test_subject,
                body=self.test_body,
                is_html=False
            )

    @patch("smtplib.SMTP", side_effect=Exception("SMTP error"))
    def test_send_email_exception_raises(self, mock_smtp):
        self.email_service.sender = "from@example.com"
        self.email_service.username = "user"
        self.email_service.password = "pass"
        self.email_service.mail_server = "smtp.example.com"
        self.email_service.mail_port = 587
        with self.assertRaises(RuntimeError):
            self.email_service.send_email(
                reply_name="Test Sender",
                reply_email="reply@example.com",
                recipient_email=self.test_email,
                subject=self.test_subject,
                body=self.test_body,
                is_html=False
            )

    def test_decode_and_format_body(self):
        theme = "#001f3f"
        org = "TestOrg"
        raw_body = "Click [Document Link] please."
        placeholder = "[Document Link]"
        link = "https://example.com"
        validity_datetime = datetime(2025, 8, 13, 12, 0)
        result = self.email_service.decode_and_format_body(theme, org, raw_body, placeholder, link, validity_datetime)
        self.assertIn('<a href="https://example.com"', result)
        self.assertIn("<html>", result)

    def test_decode_and_format_body_form(self):
        theme = "#001f3f"
        org = "TestOrg"
        raw_body = "Click [Form Link] please."
        placeholder = "[Form Link]"
        link = "https://example.com"
        validity_datetime = datetime(2025, 8, 13, 12, 0)
        result = self.email_service.decode_and_format_body_form(theme, org, raw_body, placeholder, link, validity_datetime, party_name="John")
        self.assertIn('<a href="https://example.com"', result)
        self.assertIn("<html>", result)

    @patch.object(EmailService, "send_email")
    def test_send_otp_verification_link(self, mock_send_email):
        self.email_service.send_otp_verification_link(self.test_email, "123456")
        mock_send_email.assert_called_once()
        args, kwargs = mock_send_email.call_args
        self.assertEqual(args[2], self.test_email)
        self.assertIn("OTP", args[0])
        self.assertTrue(any("123456" in str(arg) for arg in args))

    @patch("app.services.email_service.save_document_url")
    @patch("auth_app.app.services.auth_service.AuthService.get_logo_and_theme", new_callable=AsyncMock)
    @patch("auth_app.app.services.auth_service.AuthService.get_domain_by_user_email", new_callable=AsyncMock)
    @patch("app.services.email_service.get_document_name")
    @patch.object(EmailService, "send_email")
    @patch("app.services.email_service.notification_service")
    def test_send_link_success(
        self, mock_notification, mock_send_email, mock_get_document_name, mock_get_domain, mock_get_logo, mock_save_url
    ):
        mock_get_logo.return_value = {"logo": "logo.png", "theme": "#fff", "organization": "Org"}
        mock_get_domain.return_value = "domain.com"
        mock_get_document_name.return_value = "DocName"
        email_response = [EmailResponse(email_subject="Subject", email_body="Click [Document Link] please.")]
        import asyncio
        asyncio.run(self.email_service.send_link(
            reply_name="Test",
            reply_email="reply@example.com",
            recipient_email=self.test_email,
            document_id="docid",
            tracking_id="trackid",
            party_id="partyid",
            party_name="Test Party",
            token="token",
            email_response=email_response,
            validity_datetime=datetime(2025, 8, 13, 12, 0),
            cc_emails=["cc@example.com"]
        ))
        mock_send_email.assert_called_once()
        mock_notification.store_notification.assert_called()

    @patch("app.services.email_service.save_document_url")
    @patch("auth_app.app.services.auth_service.AuthService.get_logo_and_theme", new_callable=AsyncMock)
    @patch("auth_app.app.services.auth_service.AuthService.get_domain_by_user_email", new_callable=AsyncMock)
    @patch("app.services.email_service.get_document_name")
    @patch.object(EmailService, "send_email", side_effect=Exception("fail"))
    @patch("app.services.email_service.notification_service")
    def test_send_link_failure(
        self, mock_notification, mock_send_email, mock_get_document_name, mock_get_domain, mock_get_logo, mock_save_url
    ):
        mock_get_logo.return_value = {"logo": "logo.png", "theme": "#fff", "organization": "Org"}
        mock_get_domain.return_value = "domain.com"
        mock_get_document_name.return_value = "DocName"
        email_response = [EmailResponse(email_subject="Subject", email_body="Click [Document Link] please.")]
        import asyncio
        with self.assertRaises(Exception):
            asyncio.run(self.email_service.send_link(
                reply_name="Test",
                reply_email="reply@example.com",
                recipient_email=self.test_email,
                document_id="docid",
                tracking_id="trackid",
                party_id="partyid",
                party_name="Test Party",
                token="token",
                email_response=email_response,
                validity_datetime=datetime(2025, 8, 13, 12, 0),
                cc_emails=["cc@example.com"]
            ))
        mock_notification.store_notification.assert_called()

    @patch("auth_app.app.services.auth_service.AuthService.get_logo_and_theme", new_callable=AsyncMock)
    @patch.object(EmailService, "send_email")
    def test_send_signed_pdf_email(self, mock_send_email, mock_get_logo):
        mock_get_logo.return_value = {"logo": "logo.png", "theme": "#fff", "organization": "Org"}
        import asyncio
        asyncio.run(self.email_service.send_signed_pdf_email(
            document_name="TestDoc",
            reply_name="Test",
            reply_email="reply@example.com",
            recipient_email=self.test_email,
            pdf_bytes=self.test_pdf_bytes,
            email_response=self.email_response
        ))
        mock_send_email.assert_called_once()
        args = mock_send_email.call_args[1]
        self.assertEqual(args["attachment_filename"], "TestDoc")

    @patch("app.services.email_service.tracker_collection.find_one", new_callable=AsyncMock)
    @patch.object(EmailService, "send_email")
    def test_send_reminder_email_with_url(self, mock_send_email, mock_find_one):
        mock_find_one.return_value = {"document_url": "https://example.com/sign"}
        import asyncio
        asyncio.run(self.email_service.send_reminder_email(self.test_email, "track123"))
        mock_send_email.assert_called_once()

    @patch("app.services.email_service.tracker_collection.find_one", new_callable=AsyncMock)
    @patch.object(EmailService, "send_email")
    def test_send_reminder_email_no_url(self, mock_send_email, mock_find_one):
        mock_find_one.return_value = None
        import asyncio
        asyncio.run(self.email_service.send_reminder_email(self.test_email, "track123"))
        mock_send_email.assert_not_called()

    @patch("auth_app.app.services.auth_service.AuthService.get_logo_and_theme", new_callable=AsyncMock)
    @patch.object(EmailService, "send_email")
    def test_send_form_link(self, mock_send_email, mock_get_logo):
        mock_get_logo.return_value = {"logo": "logo.png", "theme": "#fff", "organization": "Org"}
        import asyncio
        asyncio.run(self.email_service.send_form_link(
            recipient_email=self.test_email,
            form_id="form123",
            party_id="party123",
            party_name="Test Party",
            token="token123",
            email_response=self.single_email_response,
            validity_datetime="2025-08-13T12:00:00",
            reply_name="Test",
            reply_email="reply@example.com",
            cc_emails=["cc@example.com"]
        ))
        mock_send_email.assert_called_once()
        self.assertIn("form-submission", mock_send_email.call_args[1]["body"])

    @patch.object(EmailService, "send_email")
    def test_send_filled_pdf_email(self, mock_send_email):
        self.email_service.send_filled_pdf_email(self.test_email, self.test_pdf_bytes)
        mock_send_email.assert_called_once()
        args = mock_send_email.call_args[1]
        self.assertEqual(args["attachment_filename"], "filled_form.pdf")

    @patch("auth_app.app.services.auth_service.AuthService.get_logo_and_theme", new_callable=AsyncMock)
    @patch.object(EmailService, "send_email")
    def test_send_credentials_email(self, mock_send_email, mock_get_logo):
        mock_get_logo.return_value = {"logo": "logo.png", "theme": "#fff", "organization": "Org"}
        import asyncio
        asyncio.run(self.email_service.send_credentials_email(
            recipient_name="User",
            recipient_email=self.test_email,
            password="pass123",
            name="Admin",
            reply_email="admin@example.com"
        ))
        mock_send_email.assert_called_once()
        args = mock_send_email.call_args[1]
        self.assertEqual(args["recipient_email"], self.test_email)
        self.assertTrue(args["is_html"])

if __name__ == "__main__":
    unittest.main()