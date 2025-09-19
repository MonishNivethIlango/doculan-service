import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from config import config

key = config.KEY  # 16 char for AES128
iv = config.IV.encode('utf-8')  # 16 char for AES128

def decrypt(enc, key, iv):
    enc = base64.b64decode(enc)
    cipher = Cipher(algorithms.AES(key.encode('utf-8')), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(enc) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()  # AES block size is 128 bits (16 bytes)
    return unpadder.update(decrypted_data) + unpadder.finalize()


def encrypt(data, key, iv):
    data = data.encode()
    padder = padding.PKCS7(128).padder()  # AES block size is 128 bits (16 bytes)
    padded_data = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key.encode('utf-8')), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(encrypted_data)


def encrypt_data(data):
    try:
        encrypted=encrypt(data, key, iv)
        return encrypted.decode("utf-8", "ignore")
    except Exception as e:
        print("Encryption error:", e)
        return None


def decrypt_data(encrypted_token):
    try:
        decrypted = decrypt(encrypted_token, key, iv)
        return decrypted.decode("utf-8", "ignore")
    except Exception as e:
        print("Decryption error:", e)
        return None

from datetime import datetime
import pytz
from datetime import datetime
import pytz

def map_date_format(format_str: str) -> str:
    return format_str.replace("DD", "%d").replace("MM", "%m").replace("YYYY", "%Y")

def map_time_format(format_str: str) -> str:
    if format_str == "12":
        return "%I:%M:%S %p %Z"  # includes seconds and timezone abbreviation
    elif format_str == "24":
        return "%H:%M:%S %Z"     # 24-hour format with seconds and timezone
    return "%H:%M:%S %Z"  # default fallback


def format_datetime(
    dt_str: str,
    date_format: str = "DD/MM/YYYY",
    time_format: str = "12",
    timezone_str: str = "UTC"
) -> str:
    try:
        if not dt_str:
            return "-"
        dt = datetime.fromisoformat(dt_str)
        tz = pytz.timezone(timezone_str)
        dt = dt.astimezone(tz)

        # Convert to actual format strings
        python_date_format = map_date_format(date_format)
        python_time_format = map_time_format(time_format)

        return dt.strftime(f"{python_date_format}, {python_time_format}")
    except Exception:
        return "-"




async def format_user_datetime(email: str, dt_str: str) -> str:
    from auth_app.app.services.auth_service import AuthService

    prefs = await AuthService().get_preferences_by_email(email)
    return format_datetime(
        dt_str,
        date_format=prefs.dateFormat,
        time_format=prefs.timeFormat,
        timezone_str=prefs.timezone
    )

