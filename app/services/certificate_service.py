import hashlib
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

env = Environment(loader=FileSystemLoader("./app/templates"))

class CertificateService:


    @staticmethod
    def render_certificate_pdf(data: dict, template_name: str = "template.html") -> bytes:
        template = env.get_template(template_name)

        html_out = template.render(**data)
        pdf_bytes = HTML(string=html_out).write_pdf()
        return pdf_bytes


    @staticmethod
    def render_form_pdf(data: dict, template_name: str = "form.html") -> bytes:
        template = env.get_template(template_name)

        html_out = template.render(**data)
        pdf_bytes = HTML(string=html_out).write_pdf()
        return pdf_bytes


    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()


certificate_service = CertificateService()



