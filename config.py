import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from os.path import join, dirname

import pytz

# Supported date formats
DATE_FORMATS = {
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYY-MM-DD": "%Y-%m-%d",
    "MMM DD, YYYY": "%b %d, %Y"
}

# Supported time formats
TIME_FORMATS = {
    "12": "%I:%M %p",
    "24": "%H:%M"
}

TIMEZONES = pytz.all_timezones

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]  # Only console output
)
dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)

# Ensure DIR is set
def read_key_from_file(file_path: Optional[str]) -> Optional[str]:
    """Reads the content of a file if the path exists."""
    if file_path and os.path.exists(file_path):
        with open(file_path, "r") as file:
            return file.read().strip()
    return None
def read_file_as_bytes(path: str) -> bytes:
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "rb") as f:
        return f.read()

class Config():
    S3_BUCKET: Optional[str] = os.getenv("S3_BUCKET")
    BASE_URL: str = os.getenv("HOST")
    MONGO_URI: Optional[str] = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB : Optional[str] = os.getenv("MONGO_DB")
    AI_SERVICE_URL : Optional[str] = os.getenv("AI_SERVICE_URL")
    AI_API_KEY: Optional[str] = os.getenv("AI_API_KEY")
    SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")
    AWS_ACCESS_KEY: Optional[str] = os.getenv("AWS_ACCESS_KEY")
    AWS_SECRET_KEY: Optional[str] = os.getenv("AWS_SECRET_KEY")
    AWS_REGION: Optional[str] ="us-east-1"
    GOOGLE_SERVICE_ACCOUNT: Optional[str] = os.getenv("GOOGLE_SERVICE_ACCOUNT")
    HOSTS: Optional[str] = os.getenv("ALLOWED_HOSTS")
    ALLOWED_HOSTS: list[str] = ["*"]
    SENTINEL_DNS: Optional[str] = os.getenv("SENTINEL_DNS")
    MAIL_USERNAME: Optional[str] = os.getenv("MAIL_USERNAME")
    SENTINEL_PORT: Optional[int] = os.getenv("SENTINEL_PORT")
    SENTINEL_SERVICE_NAME: Optional[str] = os.getenv("SENTINEL_SERVICE_NAME")
    MAIL_PASSWORD: Optional[str] = os.getenv("MAIL_PASSWORD")
    MAIL_FROM: Optional[str] = os.getenv("MAIL_FROM", "default@example.com")
    MAIL_PORT: Optional[int] = int(os.getenv("MAIL_PORT", 587))
    MAIL_SERVER: Optional[str] = os.getenv("MAIL_SERVER")
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    STORAGE_TYPE: str = "s3"
    REDIS_HOST: Optional[str] = os.getenv("REDIS_HOST")
    REDIS_PORT: Optional[int] = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: Optional[int] = int(os.getenv("REDIS_DB", 0))
    KMS_KEY_ID: Optional[str] = os.getenv("KMS_KEY_ID")
    IS_KMS_ENABLED: bool = False
    KEY: Optional[str] = os.getenv("KEY")
    IV: Optional[str] = os.getenv("IV")
    DEV_SUB: Optional[str] = os.getenv("DEV_SUB")
    PRIVATE_KEY_PATH: Optional[str] = os.getenv("PRIVATE_KEY_PATH")
    PUBLIC_KEY_PATH: Optional[str] = os.getenv("PUBLIC_KEY_PATH")
    SIGN_CERTIFICATE_PATH: Optional[str] = os.getenv("SIGN_CERTIFICATE")
    SIGN_REQUEST_CSR_PATH: Optional[str] = os.getenv("SIGN_REQUEST_CSR")
    SIGN_SIGNER_CERT_PATH: Optional[str] = os.getenv("SIGN_SIGNER_CERT")
    SIGN_PRIVATE_KEY_PATH: Optional[str] = os.getenv("SIGN_PRIVATE_KEY")

    # Loaded bytes
    SIGN_CERTIFICATE: Optional[bytes] = None
    SIGN_REQUEST_CSR: Optional[bytes] = None
    SIGN_SIGNER_CERT: Optional[bytes] = None
    SIGN_PRIVATE_KEY: Optional[bytes] = None

    AES_KEY: Optional[str] = os.getenv("AES_KEY")
    AES_IV: Optional[str] = os.getenv("AES_IV")
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY")
    ESIGN_CERT: Optional[str] = os.getenv("ESIGN_CERT")
    CERT_PASSWORD: Optional[str] = os.getenv("CERT_PASSWORD")
    DIGI_CERT_CA: Optional[str] = os.getenv("DIGI_CERT_CA")
    ACCESS_TOKEN_EXPIRE_MINUTES: Optional[int] = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_MINUTES: Optional[int] = os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES")

    ENV: str = os.getenv("ENV")
    def __init__(self):
        """If AWS credentials are stored as file paths, read them."""
        if self.SECRET_KEY and os.path.exists(self.SECRET_KEY):
            self.SECRET_KEY = read_key_from_file(self.SECRET_KEY)
        if self.AI_API_KEY and os.path.exists(self.AI_API_KEY):
            self.AI_API_KEY = read_key_from_file(self.AI_API_KEY)
        if self.AWS_ACCESS_KEY and os.path.exists(self.AWS_ACCESS_KEY):
            self.AWS_ACCESS_KEY = read_key_from_file(self.AWS_ACCESS_KEY)
        if self.AWS_SECRET_KEY and os.path.exists(self.AWS_SECRET_KEY):
            self.AWS_SECRET_KEY = read_key_from_file(self.AWS_SECRET_KEY)
        if self.KMS_KEY_ID and os.path.exists(self.KMS_KEY_ID):
            self.KMS_KEY_ID = read_key_from_file(self.KMS_KEY_ID)
        if self.KEY and os.path.exists(self.KEY):
            self.KEY = read_key_from_file(self.KEY)
        if self.IV and os.path.exists(self.IV):
            self.IV = read_key_from_file(self.IV)
        if self.CERT_PASSWORD and os.path.exists(self.CERT_PASSWORD):
            self.CERT_PASSWORD = read_key_from_file(self.CERT_PASSWORD)
        if self.STRIPE_SECRET_KEY and os.path.exists(self.STRIPE_SECRET_KEY):
            self.STRIPE_SECRET_KEY = read_key_from_file(self.STRIPE_SECRET_KEY)
        if self.SIGN_CERTIFICATE_PATH and os.path.exists(self.SIGN_CERTIFICATE_PATH):
            self.SIGN_CERTIFICATE = read_file_as_bytes(self.SIGN_CERTIFICATE_PATH)
        if self.SIGN_REQUEST_CSR_PATH and os.path.exists(self.SIGN_REQUEST_CSR_PATH):
            self.SIGN_REQUEST_CSR = read_file_as_bytes(self.SIGN_REQUEST_CSR_PATH)
        if self.SIGN_SIGNER_CERT_PATH and os.path.exists(self.SIGN_SIGNER_CERT_PATH):
            self.SIGN_SIGNER_CERT = read_file_as_bytes(self.SIGN_SIGNER_CERT_PATH)
        if self.SIGN_PRIVATE_KEY_PATH and os.path.exists(self.SIGN_PRIVATE_KEY_PATH):
            self.SIGN_PRIVATE_KEY = read_file_as_bytes(self.SIGN_PRIVATE_KEY_PATH)
config=Config()

print(config.ESIGN_CERT)