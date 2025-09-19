from typing import Optional
from dotenv import load_dotenv
import os
from os.path import join, dirname


# Load environment variables from .env file
dotenv_path = join(dirname(__file__), ".env")
load_dotenv(dotenv_path)


def read_key_from_file(file_path: Optional[str]) -> Optional[str]:
    """Reads the content of a file if the path exists."""
    if file_path and os.path.exists(file_path):
        with open(file_path, "r") as file:
            return file.read().strip()
    return None

class Settings:
    PDF_FOLDER: str = "pdfs/"
    FAISS_INDEX_PATH: Optional[str] = os.getenv("FAISS_INDEX_PATH")
    JWT_SECRET_KEY: Optional[str] = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM: Optional[str] = os.getenv("JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: Optional[str] = os.getenv("JWT_ALGORITHM")
    ALLOWED_HOSTS: list[str] = []
    DB_NAME: Optional[str] = os.getenv("DB_NAME")
    MONGO_URI: Optional[str] = os.getenv("MONGO_URI")



# Instantiate Settings
settings = Settings()