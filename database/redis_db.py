import random
import redis
from config import config
from redis.sentinel import Sentinel

redis_host = config.REDIS_HOST
redis_port = config.REDIS_PORT
redis_db = config.REDIS_DB
sentinel_dns = config.SENTINEL_DNS
sentinel_port = config.SENTINEL_PORT
sentinel_service_name = config.SENTINEL_SERVICE_NAME

if config.ENV=="dev":
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
elif config.ENV=="prod":
    sentinel = Sentinel([(sentinel_dns, sentinel_port)], socket_timeout=0.5)
    redis_client = sentinel.master_for(service_name=sentinel_service_name, socket_timeout=0.5)
OTP_EXPIRY_SECONDS = 15 * 60  # 5 minutes



# sentinel_dns = 'redis.internal.redis-app.com'  # Your DNS that resolves to all sentinel IPs
# sentinel_port = 26379
# sentinel_service_name=mymaster



def generate_otp(party_id, tracking_id):
    otp = str(random.randint(100000, 999999))
    redis_key = f"otp:{party_id}:{tracking_id}"
    redis_client.setex(redis_key, OTP_EXPIRY_SECONDS, otp)  # Set with expiry
    return otp


def verify_otp(party_id, tracking_id, otp):
    redis_key = f"otp:{party_id}:{tracking_id}"
    stored_otp = redis_client.get(redis_key)
    if stored_otp and stored_otp.decode() == otp:
        redis_client.delete(redis_key)  # Optional: delete after successful verification
        return True
    return False

def generate_form_otp(form_id, party_email):
    otp = str(random.randint(100000, 999999))
    redis_key = f"otp:{form_id}:{party_email}"
    redis_client.setex(redis_key, OTP_EXPIRY_SECONDS, otp)  # Set with expiry
    return otp

def verify_form_otp(form_id, party_email, otp):
    redis_key = f"otp:{form_id}:{party_email}"
    stored_otp = redis_client.get(redis_key)
    if stored_otp and stored_otp.decode() == otp:
        redis_client.delete(redis_key)  # Optional: delete after successful verification
        return True
    return False