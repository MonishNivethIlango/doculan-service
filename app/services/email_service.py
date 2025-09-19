import asyncio
import os
from datetime import datetime
from email.utils import formataddr
from typing import Union, Optional, List
import io
from smtplib import SMTPException

from fastapi import HTTPException
from jinja2 import FileSystemLoader, Environment

from app.schemas.form_schema import EmailResponse
from app.services.notification_service import notification_service
from auth_app.app.database.connection import save_document_url, tracker_collection
from config import config
import base64

from repositories.s3_repo import get_document_name
from utils.logger import logger


class EmailService:
    def __init__(self):
        self.mail_server = config.MAIL_SERVER
        self.mail_port = config.MAIL_PORT
        self.username = config.MAIL_USERNAME
        self.password = config.MAIL_PASSWORD
        self.sender = config.MAIL_FROM
        self.base_url = config.BASE_URL
        BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # <- goes up from /services to /app
        templates_dir = os.path.join(BASE_DIR, "templates")
        self.env = Environment(loader=FileSystemLoader(templates_dir))


    def send_email(
        self,
        reply_name: str,
        reply_email: str,
        recipient_email: str,
        subject: str,
        body: str,
        attachment_bytes=None,
        attachment_filename=None,
        is_html: bool = False,
        inline_images: Optional[dict] = None,
        cc_emails: Optional[List[str]] = None
    ):
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.image import MIMEImage
        from email.mime.application import MIMEApplication
        import smtplib, io, base64
        from email.utils import formataddr
        message = MIMEMultipart("related")
        sender_email = self.sender
        message["From"] = formataddr((reply_name, sender_email))
        message.add_header("Reply-To", reply_email)
        message["To"] = recipient_email
        message["Subject"] = subject
        if cc_emails:
            message["Cc"] = ", ".join(cc_emails)

        msg_alternative = MIMEMultipart("alternative")
        message.attach(msg_alternative)
        msg_alternative.attach(MIMEText(body, "html" if is_html else "plain"))

        # Attach inline images
        if inline_images:
            for cid, img_path in inline_images.items():
                if img_path.startswith("data:image/"):  # base64 inline image
                    header, encoded = img_path.split(",", 1)
                    img_file = io.BytesIO(base64.b64decode(encoded))
                else:
                    img_file = open(img_path, "rb")

                with img_file:
                    mime_img = MIMEImage(img_file.read())
                    mime_img.add_header("Content-ID", f"<{cid}>")
                    mime_img.add_header("Content-Disposition", "inline")
                    message.attach(mime_img)

        # Attach files
        if attachment_bytes and attachment_filename:
            part = MIMEApplication(attachment_bytes, Name=attachment_filename)
            part["Content-Disposition"] = f'attachment; filename="{attachment_filename}"'
            message.attach(part)

        # Send email
        try:
            with smtplib.SMTP(self.mail_server, self.mail_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                all_recipients = [recipient_email] + (cc_emails if cc_emails else [])
                result = server.sendmail(sender_email, all_recipients, message.as_string())

                # Check if any recipient failed
                if result:  # non-empty dict = failure
                    raise RuntimeError(f"Failed recipients: {result}")

        except Exception as e:
            raise RuntimeError(f"Failed to send email to {recipient_email}: {e}") from e

    @staticmethod
    def decode_and_format_body_form(theme: str,org: str,
            raw_body: str,
            placeholder: str,
            replacement_link: str,
            validity_datetime: Union[str, datetime],
            party_name: str = None
    ) -> str:
        decoded_body = raw_body.encode().decode('unicode_escape')

        # Step 2: Replace placeholders like [Fullname] or [Recipient's Name]

        logger.info(f"{decoded_body} party_name")
        if party_name:
            for placeholder in ["[Fullname]", "[Recipient's Name]"]:
                decoded_body = decoded_body.replace(placeholder, party_name)
        else:
            decoded_body = decoded_body.replace("[Fullname]", "")

        # Replace placeholder with a styled button

        html_body_with_br = decoded_body.replace('\n', '<br>')
        html_body_with_br = html_body_with_br.replace(
            "[Form Link]",
            f"""
                    <!-- Button -->
                      <table border="0" cellspacing="0" cellpadding="0" align="center" style="margin-top:30px;">
                        <tr>
                          <td align="center">
                            <a href="{replacement_link}" class="btn">
                              <img src="https://img.icons8.com/?size=100&id=69622&format=png&color=000000" alt="PDF Icon" />
                              View, Review & Complete the Form
                            </a>
                          </td>
                        </tr>
                      </table>

                      <!-- Click Here fallback -->
                      <p style="text-align:center; margin-top:15px;">
                        <a href="{replacement_link}" style="color:#0066cc; text-decoration:underline;">
                          Click Here
                        </a>
                      </p>
                    """
        )
        # Handle validity datetime
        if isinstance(validity_datetime, str):
            validity_dt = datetime.fromisoformat(validity_datetime)
        else:
            validity_dt = validity_datetime

        formatted_validity = validity_dt.strftime("%Y-%m-%d %H:%M %Z") or validity_dt.strftime("%Y-%m-%d %H:%M")

        # Load template
        BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # <- goes up from /services to /app
        templates_dir = os.path.join(BASE_DIR, "templates")
        env = Environment(loader=FileSystemLoader(templates_dir))
        template = env.get_template("email_form_template.html")

        # Render template
        rendered_html = template.render(
            theme=theme,
            org=org,
            html_body_with_br=html_body_with_br,
            formatted_validity=formatted_validity
        )

        return rendered_html

    @staticmethod
    def decode_and_format_body(
            theme: str,
            org: str,
            raw_body: str,
            placeholder: str,
            replacement_link: str,
            validity_datetime: Union[str, datetime],
            party_name: str = None
    ) -> str:
        # Step 1: Decode raw body
        decoded_body = raw_body.encode().decode('unicode_escape')

        # Step 2: Replace placeholders (without button inline)
        html_body = decoded_body
        if party_name:
            for placeholder in ["[Fullname]", "[Recipient's Name]"]:
                html_body = html_body.replace(placeholder, party_name)

        else:
            html_body = html_body.replace("[Fullname]", "")

        html_body_ = html_body.replace('\n', '<br>')
        html_body_with_br = html_body_.replace(
            "[Document Link]",
            f"""
            <!-- Button -->
              <table border="0" cellspacing="0" cellpadding="0" align="center" style="margin-top:30px;">
                <tr>
                  <td align="center">
                    <a href="{ replacement_link }" class="btn">
                      <img src="https://img.icons8.com/ios-filled/24/cc0000/pdf.png" alt="PDF Icon" />
                      View, Review &amp; Sign Document
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Click Here fallback -->
              <p style="text-align:center; margin-top:15px;">
                <a href="{ replacement_link }" style="color:#0066cc; text-decoration:underline;">
                  Click Here
                </a>
              </p>
            """
        )

        # Step 3: Format validity date
        if isinstance(validity_datetime, str):
            validity_dt = datetime.fromisoformat(validity_datetime)
        else:
            validity_dt = validity_datetime

        formatted_validity = validity_dt.strftime("%Y-%m-%d %H:%M %Z")

        # Step 5: Load Jinja template
        BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # <- goes up from /services to /app
        templates_dir = os.path.join(BASE_DIR, "templates")
        env = Environment(loader=FileSystemLoader(templates_dir))
        template = env.get_template("email.html")
        # Step 6: Render with variables
        full_html = template.render(
            theme=theme,
            org=org,
            html_body_with_br=html_body_with_br,
            replacement_link = replacement_link,
            formatted_validity=formatted_validity,
        )

        return full_html

    def send_otp_verification_link(self, recipient_email: str, otp: str):
        subject = "OTP Verification for Document"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0px 0px 10px #e0e0e0;">
                <h2 style="color: #333333;">OTP Verification for Document</h2>
                <p>Your One-Time Password (OTP) is:</p>
                <div style="font-size: 18px; font-weight: bold; margin: 20px 0; padding: 10px; background-color: #f0f0f0; text-align: center; border-radius: 5px;">
                    <span style="color: #2E86C1;">{otp}</span>
                </div>
                <p><strong>Validity:</strong> 15 minutes</p>
                <p>If you did not request this code, please contact us at <a href="mailto:vigensh.v@virtualansoftware.com">vigensh.v@virtualansoftware.com</a>.</p>
            </div>
        </body>
        </html>
        """
        reply_name = "OTP Verification"
        reply_email = "support@doculan.ai"
        self.send_email(reply_name, reply_email, recipient_email, subject, body, is_html=True)

    async def send_link(
        self,
        reply_name: str,
        reply_email: str,
        recipient_email: str,
        document_id: str,
        tracking_id: str,
        party_id: str,
        party_name: str,
        token: str,
        email_response,
        validity_datetime,
        cc_emails: Optional[List[str]] = None
    ):
        from auth_app.app.services.auth_service import AuthService

        subject = email_response[0].email_subject
        raw_body = email_response[0].email_body

        document_url = f"{self.base_url}/signing?document_id={document_id}&tracking_id={tracking_id}&party_id={party_id}&token={token}"
        save_document_url(tracking_id, document_url)

        # Remove duplicates + avoid sending CC to recipient itself
        cc_list_cleaned = list(
            set(email.lower() for email in (cc_emails or []) if email.lower() != recipient_email.lower())
        )

        # Branding info
        user_style = await AuthService().get_logo_and_theme(reply_email)
        theme = "#0EA5E9"
        logo = "images/doculan-logo.png"
        org = "Doculan"
        if user_style:
            logo = user_style.get("logo") if user_style.get("logo") != "string" else logo
            theme = user_style.get("theme") if user_style.get("theme") != "string" else theme
            org = user_style.get("organization", org)

        domain_name = await AuthService.get_domain_by_user_email(reply_email)
        document_name = get_document_name(domain_name, document_id)
        logger.info(f"{domain_name}- document-name{document_name}")
        email_body = self.decode_and_format_body(
            theme,
            org,
            raw_body,
            "[Document Link]",
            document_url,
            validity_datetime,
            party_name=party_name
        )

        # Try sending email
        try:
            self.send_email(
                recipient_email=recipient_email,
                subject=subject,
                body=email_body,
                is_html=True,
                inline_images={"company_logo": f"{logo}"},
                cc_emails=cc_list_cleaned,
                reply_name=reply_name,
                reply_email=reply_email
            )
            notification_service.store_notification(
                email=domain_name,
                user_email=reply_email,
                document_id=document_id,
                tracking_id=tracking_id,
                document_name=document_name,
                parties_status=[{"id": party_id, "name": party_name, "email": recipient_email}],
                timestamp=datetime.utcnow().isoformat(),
                action="dispatched",
                party_name=party_name,
                party_email=recipient_email
            )
        except Exception as e:
            # ❌ Email failed → store notification as failed
            notification_service.store_notification(
                email=domain_name,
                user_email=reply_email,
                document_id=document_id,
                tracking_id=tracking_id,
                document_name=document_name,
                parties_status=[{"id": party_id, "name": party_name, "email": recipient_email}],
                timestamp=datetime.utcnow().isoformat(),
                action="failed",
                party_name=party_name,
                party_email=recipient_email,
                reason=str(e)
            )
            # Stop API request with 400 instead of 500
            raise HTTPException(
                status_code=400,
                detail=f"Failed to send email to {recipient_email}: {str(e)}"
            ) from e

    async def send_signed_pdf_email(self, document_name : str, reply_name: str,
            reply_email: str, recipient_email: str, pdf_bytes: bytes, email_response):
        subject = email_response[0].email_subject
        from auth_app.app.services.auth_service import AuthService

        user_style = await AuthService().get_logo_and_theme(reply_email)
        theme = "#0EA5E9"
        logo = "images/doculan-logo.png"
        org = "Doculan"
        if user_style:
            print("Logo:", user_style["logo"])
            print("Theme:", user_style["theme"])
            logo = user_style["logo"]
            if logo == "string":
                logo = "images/doculan-logo.png"
            theme = user_style["theme"]
            if theme == "string":
                theme = "#0EA5E9"
            org = user_style["organization"]
        subject = f"{subject} - Completed"

        body = f"""
        <html>
          <head>
            <style>
                body {{
                    background-color: {theme};
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 40px 0;
                }}
                .email-wrapper {{
                    max-width: 600px;
                    margin: auto;
                    background-color: #ffffff;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                }}
                .header {{
                    background-color: {theme};
                    text-align: center;
                    padding: 30px;
                }}
                .header img {{
                    max-height: 50px;
                }}
                .content {{
                    padding: 40px 30px;
                    color: #333333;
                }}
                .content h2 {{
                    color: #000053;
                    font-size: 22px;
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .content p {{
                    font-size: 15px;
                    line-height: 1.6;
                    margin: 10px 0;
                }}
                .attachment-box {{
                    background-color: #f9f9f9;
                    border-left: 4px solid {theme};
                    padding: 15px 20px;
                    margin-top: 30px;
                    border-radius: 5px;
                    color: {theme};
                    font-size: 14px;
                }}
                .footer {{
                    padding: 20px;
                    text-align: center;
                    font-size: 13px;
                    color: #999999;
                    background-color: #f0f0f0;
                    border-top: 1px solid #e0e0e0;
                }}
                a {{
                    color: #000053;
                    text-decoration: none;
                }}
            </style>
          </head>
          <body>
            <div class="email-wrapper">
                <div class="header">
                    <img src="cid:company_logo" alt="Company Logo" />
                    <p style="margin: 10px 0 0 0; font-weight: bold; color: #ffffff; font-size: 14px;">{org}</p>
                </div>
                <div class="content">
                    <h2>Signed Document Confirmation</h2>
                    <p>Hello,</p>
                    <p>Thank you for completing the document signing process. Your signed document is attached for your records.</p>
                    <p>If you have any questions or require further assistance, please contact our support team at 
                        <a href="mailto:support@doculan.ai">support@doculan.ai</a>.
                    </p>
                    <div class="attachment-box">
                        📎 <strong>Attached:</strong> <em>{document_name}</em><br>
                        Please download the signed document from the attachments section of this email.
                    </div>
                </div>
                <div class="footer">
                    &copy; {datetime.now().year} Virtualan Software. All rights reserved.
                </div>
            </div>
          </body>
        </html>
        """

        self.send_email(
        reply_name = reply_name,
        reply_email = reply_email,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            attachment_bytes=pdf_bytes,
            attachment_filename=f"{document_name}",
            is_html=True,
            inline_images={"company_logo": f"{logo}"}
        )

    async def send_reminder_email(self, email: str, tracking_id: str):
        doc = await tracker_collection.find_one({"tracking_id": tracking_id})
        document_url = doc.get("document_url") if doc else None
        if document_url:
            subject = "Reminder: Your signature is pending"
            body = f"""
            <html><body style="font-family: Arial, sans-serif;">
                <p>This is a reminder to complete your document signature.</p>
                <p><a href="{document_url}" style="color: #2a7ae2;">Click here to sign</a></p>
                <p>Regards,<br>Virtualan Software</p>
            </body></html>
            """
            self.send_email("DoculanSign","support@doculan.ai",email, subject, body, is_html=True)
        else:
            print(f"❌ No document URL found for tracking_id: {tracking_id}")

    def run_send_reminder_email(self, email: str, tracking_id: str):
        asyncio.run(self.send_reminder_email(email, tracking_id))

    async def send_form_link(
            self,
            recipient_email: str,
            form_id: str,
            party_id: str,
            party_name :str,
            token: str,
            email_response: EmailResponse,
            validity_datetime: str,
            reply_name: Optional[str] = None,
            reply_email: Optional[str] = None,
            cc_emails: Optional[List[str]] = None
    ):
        subject = email_response.email_subject
        raw_body = email_response.email_body


        form_url = f"{self.base_url}/form-submission?form_id={form_id}&party_id={party_id}&party_email={recipient_email}&token={token}"
        from auth_app.app.services.auth_service import AuthService

        # Branding info
        user_style = await AuthService().get_logo_and_theme(reply_email)
        theme = "#0EA5E9"
        logo = "images/doculan-logo.png"
        org = "Doculan"
        if user_style:
            logo = user_style.get("logo") if user_style.get("logo") != "string" else logo
            theme = user_style.get("theme") if user_style.get("theme") != "string" else theme
            org = user_style.get("organization", org)
        html_body = self.decode_and_format_body_form(theme,org,raw_body, '[Form Link]', form_url, validity_datetime,party_name)

        self.send_email(
            reply_name=reply_name,
            reply_email=reply_email,
            inline_images={"company_logo": f"{logo}"},
            recipient_email=recipient_email,
            subject=subject,
            body=html_body,
            is_html=True,
            cc_emails=cc_emails
        )

    def send_filled_pdf_email(
            self,
            to_email: str,
            pdf_bytes: bytes,
            reply_name: Optional[str] = None,
            reply_email: Optional[str] = None,
            cc_emails: Optional[List[str]] = None
    ) -> None:
        """
        Send an email with the filled PDF form attached.

        Parameters:
        - to_email: recipient email address
        - pdf_bytes: PDF content in bytes
        - reply_name: name to show in the reply-to field (default: 'Team')
        - reply_email: email to show in the reply-to field (default: 'noreply@example.com')
        - cc_emails: list of emails to CC (optional)
        """
        subject = "Your filled form submission"
        body = """
        <html><body>
            <p>Dear user,</p>
            <p>Thank you for completing the form.</p>
            <p>Please find your filled form attached as a PDF.</p>
            <p>Regards,<br>Team</p>
        </body></html>
        """

        self.send_email(
            reply_name=reply_name or "Team",
            reply_email=reply_email or "noreply@example.com",
            recipient_email=to_email,
            subject=subject,
            body=body,
            attachment_bytes=pdf_bytes,
            attachment_filename="filled_form.pdf",
            is_html=True,
            cc_emails=cc_emails
        )


    async def send_credentials_email(self, recipient_name: str, recipient_email: str, password: str, name: str, reply_email):
        template = self.env.get_template("credentials_email.html")

        from auth_app.app.services.auth_service import AuthService
        login_url = f"{config.BASE_URL.rstrip('/')}/login"
        user_style = await AuthService().get_logo_and_theme(reply_email)
        theme = "#0EA5E9"
        logo = "images/doculan-logo.png"
        org = "Doculan"
        if user_style:
            print("Logo:", user_style["logo"])
            print("Theme:", user_style["theme"])
            logo = user_style["logo"]
            if logo == "string":
                logo = "images/doculan-logo.png"
            theme = user_style["theme"]
            if theme == "string":
                theme = "#0EA5E9"
            org = user_style["organization"]
        body = template.render(
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            password=password,
            login_url=login_url,
            org=org
        )

        subject = f"Welcome to {org} – Your Doculan Account Login Details"
        reply_name = name
        reply_email = reply_email

        self.send_email(
            reply_name=reply_name,
            reply_email=reply_email,
            recipient_email=recipient_email,
            subject=subject,
            body=body,  # rendered HTML template
            is_html=True  # 👈 VERY IMPORTANT
        )

email_service = EmailService()