import sys
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi import HTTPException

# Patch DB module to avoid Motor/async loop issues
sys.modules['auth_app.app.database.connection'] = MagicMock(
    db=MagicMock(),
    save_document_url=MagicMock(),
    tracker_collection=MagicMock()
)

from app.services.email_service import EmailService


class TestEmailServiceSync(unittest.TestCase):
    def setUp(self):
        self.email_service = EmailService()
        # Override SMTP creds to safe test values
        self.email_service.sender = "from@example.com"
        self.email_service.username = "user"
        self.email_service.password = "pass"
        self.email_service.mail_server = "smtp.example.com"
        self.email_service.mail_port = 587
        self.recipient = "to@example.com"

    @patch("smtplib.SMTP")
    def test_send_email_plain_success(self, mock_smtp):
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        server.sendmail.return_value = {}

        self.email_service.send_email(
            reply_name="Sender",
            reply_email="reply@example.com",
            recipient_email=self.recipient,
            subject="Subject",
            body="Plain text",
            is_html=False,
        )

        server.starttls.assert_called_once()
        server.login.assert_called_once_with("user", "pass")
        server.sendmail.assert_called_once()
        data = server.sendmail.call_args[0][2]
        self.assertIn("Content-Type: text/plain", data)

    @patch("smtplib.SMTP")
    def test_send_email_html_with_cc_and_inline_image(self, mock_smtp):
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        server.sendmail.return_value = {}

        inline_images = {
            # Base64 data URI path
            "company_logo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
        }
        cc_emails = ["cc1@example.com", "cc2@example.com"]
        self.email_service.send_email(
            reply_name="Sender",
            reply_email="reply@example.com",
            recipient_email=self.recipient,
            subject="HTML",
            body="<b>Hello</b>",
            is_html=True,
            inline_images=inline_images,
            cc_emails=cc_emails,
        )

        server.sendmail.assert_called_once()
        sender, recipients, data = server.sendmail.call_args[0]
        # CCs included in SMTP recipients
        self.assertIn(self.recipient, recipients)
        self.assertIn("cc1@example.com", recipients)
        self.assertIn("cc2@example.com", recipients)
        # Proper headers
        self.assertIn("Cc: cc1@example.com, cc2@example.com", data)
        self.assertIn("Content-Type: text/html", data)

    @patch("smtplib.SMTP")
    def test_send_email_with_attachment(self, mock_smtp):
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        server.sendmail.return_value = {}

        self.email_service.send_email(
            reply_name="Sender",
            reply_email="reply@example.com",
            recipient_email=self.recipient,
            subject="Attachment",
            body="See attachment",
            is_html=False,
            attachment_bytes=b"%PDF-1.4",
            attachment_filename="file.pdf",
        )

        server.sendmail.assert_called_once()
        data = server.sendmail.call_args[0][2]
        self.assertIn('filename="file.pdf"', data)

    @patch("smtplib.SMTP")
    def test_send_email_failure_from_sendmail_result(self, mock_smtp):
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        # Non-empty dict indicates failures for some recipients
        server.sendmail.return_value = {"to@example.com": (550, b"error")}

        with self.assertRaises(RuntimeError) as ctx:
            self.email_service.send_email(
                reply_name="Sender",
                reply_email="reply@example.com",
                recipient_email=self.recipient,
                subject="Subject",
                body="Body",
                is_html=False,
            )
        self.assertIn("Failed recipients", str(ctx.exception))

    @patch("smtplib.SMTP", side_effect=Exception("SMTP broken"))
    def test_send_email_exception_wrapped(self, _):
        with self.assertRaises(RuntimeError) as ctx:
            self.email_service.send_email(
                reply_name="Sender",
                reply_email="reply@example.com",
                recipient_email=self.recipient,
                subject="Subject",
                body="Body",
                is_html=False,
            )
        self.assertIn("Failed to send email", str(ctx.exception))

    @patch("app.services.email_service.Environment")
    def test_decode_and_format_body_includes_link_and_replacements(self, mock_env_cls):
        # Fake template: echo html_body_with_br wrapped in <html> for assertions
        mock_tpl = MagicMock()
        mock_tpl.render.side_effect = lambda **kw: f"<html>{kw['html_body_with_br']}</html>"
        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_tpl
        mock_env_cls.return_value = mock_env

        html = self.email_service.decode_and_format_body(
            theme="#123456",
            org="Org",
            raw_body="Hi [Fullname], see [Document Link].",
            placeholder="[Document Link]",
            replacement_link="https://x.test/doc",
            validity_datetime=datetime(2025, 1, 1, 10, 0),
            party_name="Alice",
        )
        self.assertIn("<html>", html)
        self.assertIn("Alice", html)
        self.assertIn('href="https://x.test/doc"', html)

    @patch("app.services.email_service.Environment")
    def test_decode_and_format_body_form_without_name_and_iso_datetime(self, mock_env_cls):
        mock_tpl = MagicMock()
        mock_tpl.render.side_effect = lambda **kw: f"<html>{kw['html_body_with_br']}</html>"
        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_tpl
        mock_env_cls.return_value = mock_env

        html = self.email_service.decode_and_format_body_form(
            theme="#0EA5E9",
            org="Org",
            raw_body="Please use [Form Link]",
            placeholder="[Form Link]",
            replacement_link="https://x.test/form",
            validity_datetime="2025-08-13T12:00:00",
            party_name=None,
        )
        self.assertIn("<html>", html)
        self.assertIn('href="https://x.test/form"', html)

    @patch("smtplib.SMTP")
    def test_send_email_with_multiple_cc_and_inline_images(self, mock_smtp):
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        server.sendmail.return_value = {}

        inline_images = {
            "logo1": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA",
            "logo2": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUB"
        }
        cc_emails = ["cc1@example.com", "cc2@example.com", "cc3@example.com"]
        self.email_service.send_email(
            reply_name="Sender",
            reply_email="reply@example.com",
            recipient_email=self.recipient,
            subject="HTML with multiple CC and images",
            body="<b>Hello</b>",
            is_html=True,
            inline_images=inline_images,
            cc_emails=cc_emails,
        )

        server.sendmail.assert_called_once()
        sender, recipients, data = server.sendmail.call_args[0]
        self.assertIn(self.recipient, recipients)
        for cc in cc_emails:
            self.assertIn(cc, recipients)
        self.assertIn("Cc: cc1@example.com, cc2@example.com, cc3@example.com", data)
        self.assertIn("Content-Type: text/html", data)
        self.assertIn("logo1", data)
        self.assertIn("logo2", data)

    @patch("app.services.email_service.Environment")
    def test_decode_and_format_body_with_no_party_name(self, mock_env_cls):
        mock_tpl = MagicMock()
        mock_tpl.render.side_effect = lambda **kw: f"<html>{kw['html_body_with_br']}</html>"
        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_tpl
        mock_env_cls.return_value = mock_env

        html = self.email_service.decode_and_format_body(
            theme="#123456",
            org="Org",
            raw_body="Hi [Fullname], see [Document Link].",
            placeholder="[Document Link]",
            replacement_link="https://x.test/doc",
            validity_datetime=datetime(2025, 1, 1, 10, 0),
            party_name=None,
        )
        self.assertIn("<html>", html)
        self.assertNotIn("Alice", html)
        self.assertIn('href="https://x.test/doc"', html)

    @patch("app.services.email_service.Environment")
    def test_decode_and_format_body_form_with_party_name(self, mock_env_cls):
        mock_tpl = MagicMock()
        mock_tpl.render.side_effect = lambda **kw: f"<html>{kw['html_body_with_br']}</html>"
        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_tpl
        mock_env_cls.return_value = mock_env

        html = self.email_service.decode_and_format_body_form(
            theme="#0EA5E9",
            org="Org",
            raw_body="Please use [Form Link], [Fullname]",
            placeholder="[Form Link]",
            replacement_link="https://x.test/form",
            validity_datetime="2025-08-13T12:00:00",
            party_name="Bob",
        )
        self.assertIn("<html>", html)
        self.assertIn('href="https://x.test/form"', html)
        self.assertIn("Bob", html)

    @patch.object(EmailService, "send_email")
    def test_send_filled_pdf_email_defaults(self, mock_send_email):
        # No reply_name/reply_email/cc_emails provided
        self.email_service.send_filled_pdf_email(
            to_email=self.recipient,
            pdf_bytes=b"%PDF-1.4 test"
        )
        mock_send_email.assert_called_once()
        kwargs = mock_send_email.call_args.kwargs
        self.assertEqual(kwargs["attachment_filename"], "filled_form.pdf")
        self.assertTrue(kwargs["is_html"])
        self.assertEqual(kwargs["reply_name"], "Team")
        self.assertEqual(kwargs["reply_email"], "noreply@example.com")

    @patch.object(EmailService, "send_email")
    def test_send_otp_verification_link(self, mock_send_email):
        otp = "654321"
        self.email_service.send_otp_verification_link(self.recipient, otp)
        mock_send_email.assert_called_once()
        args, kwargs = mock_send_email.call_args
        # The OTP is in the body (args[4] if positional, or kwargs["body"])
        body = args[4] if len(args) > 4 else kwargs.get("body", "")
        self.assertIn("OTP Verification", args)
        self.assertIn(self.recipient, args)
        self.assertIn(otp, body)

    def test_decode_and_format_body_form_replaces_fullname(self):
        html = self.email_service.decode_and_format_body_form(
            theme="#0EA5E9",
            org="Org",
            raw_body="Please use [Form Link], [Fullname]",
            placeholder="[Form Link]",
            replacement_link="https://x.test/form",
            validity_datetime="2025-08-13T12:00:00",
            party_name="Test User",
        )
        self.assertIn("<html>", html)
        self.assertIn('href="https://x.test/form"', html)
        self.assertIn("Test User", html)

    def test_decode_and_format_body_form_handles_datetime_object(self):
        html = self.email_service.decode_and_format_body_form(
            theme="#0EA5E9",
            org="Org",
            raw_body="Please use [Form Link]",
            placeholder="[Form Link]",
            replacement_link="https://x.test/form",
            validity_datetime=datetime(2025, 8, 13, 12, 0),
            party_name=None,
        )
        self.assertIn("<html>", html)
        self.assertIn('href="https://x.test/form"', html)
        self.assertIn("2025-08-13", html)

    def test_decode_and_format_body_replaces_fullname(self):
        html = self.email_service.decode_and_format_body(
            theme="#123456",
            org="Org",
            raw_body="Hi [Fullname], see [Document Link].",
            placeholder="[Document Link]",
            replacement_link="https://x.test/doc",
            validity_datetime=datetime(2025, 1, 1, 10, 0),
            party_name="Alice",
        )
        self.assertIn("<html>", html)
        self.assertIn("Alice", html)
        self.assertIn('href="https://x.test/doc"', html)

    def test_decode_and_format_body_handles_datetime_string(self):
        html = self.email_service.decode_and_format_body(
            theme="#123456",
            org="Org",
            raw_body="Hi [Fullname], see [Document Link].",
            placeholder="[Document Link]",
            replacement_link="https://x.test/doc",
            validity_datetime="2025-01-01T10:00:00",
            party_name=None,
        )
        self.assertIn("<html>", html)
        self.assertIn('href="https://x.test/doc"', html)
        self.assertIn("2025-01-01", html)

    @patch("app.services.email_service.save_document_url")
    @patch("auth_app.app.services.auth_service.AuthService.get_logo_and_theme", new_callable=AsyncMock)
    @patch("auth_app.app.services.auth_service.AuthService.get_domain_by_user_email", new_callable=AsyncMock)
    @patch("app.services.email_service.get_document_name")
    @patch.object(EmailService, "send_email")
    @patch("app.services.email_service.notification_service.store_notification")
    async def test_send_link_with_no_cc_emails(
        self,
        mock_store_notification,
        mock_send_email,
        mock_get_document_name,
        mock_get_domain,
        mock_get_logo,
        mock_save_url
    ):
        mock_get_logo.return_value = {"logo": "logo.png", "theme": "#fff", "organization": "Org"}
        mock_get_domain.return_value = "domain.com"
        mock_get_document_name.return_value = "DocName"
        await self.email_service.send_link(
            reply_name="Test",
            reply_email="reply@example.com",
            recipient_email=self.recipient,
            document_id="docid",
            tracking_id="trackid",
            party_id="partyid",
            party_name="Test Party",
            token="token",
            email_response=[MagicMock(email_subject="Subject", email_body="Click [Document Link] please.")],
            validity_datetime=datetime(2025, 8, 13, 12, 0),
            cc_emails=None
        )
        mock_send_email.assert_called_once()
        mock_store_notification.assert_called()
        kwargs = mock_send_email.call_args.kwargs
        self.assertNotIn("cc_emails", kwargs or {})

    @patch("app.services.email_service.tracker_collection")
    @patch.object(EmailService, "send_email")
    async def test_send_reminder_email_with_url_and_custom_subject(self, mock_send_email, mock_tracker):
        mock_tracker.find_one = AsyncMock(return_value={"document_url": "https://example.com/sign"})
        await self.email_service.send_reminder_email(self.recipient, "trk999")
        mock_send_email.assert_called_once()
        args, _kwargs = mock_send_email.call_args
        self.assertIn("support@doculan.ai", args)
        self.assertIn("Reminder: Your signature is pending", args)

    @patch("app.services.email_service.tracker_collection")
    @patch.object(EmailService, "send_email")
    async def test_send_reminder_email_no_url_logs(self, mock_send_email, mock_tracker):
        mock_tracker.find_one = AsyncMock(return_value=None)
        with patch("builtins.print") as mock_print:
            await self.email_service.send_reminder_email(self.recipient, "trk999")
            mock_send_email.assert_not_called()
            mock_print.assert_called()
            self.assertIn("No document URL found", mock_print.call_args[0][0])


if __name__ == "__main__":
    unittest.main()