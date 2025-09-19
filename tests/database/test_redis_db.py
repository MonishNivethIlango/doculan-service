from unittest.mock import patch, MagicMock
import random
import app
import importlib

def test_generate_and_verify_otp():
    with patch('database.redis_db.redis_client') as mock_redis:
        # Patch random to return a fixed OTP
        with patch('database.redis_db.random.randint', return_value=123456):
            from database import redis_db
            otp = redis_db.generate_otp('party1', 'track1')
            assert otp == '123456'
            mock_redis.setex.assert_called_with('otp:party1:track1', redis_db.OTP_EXPIRY_SECONDS, '123456')
            # Simulate correct OTP in redis
            mock_redis.get.return_value = b'123456'
            assert redis_db.verify_otp('party1', 'track1', '123456') is True
            mock_redis.delete.assert_called_with('otp:party1:track1')
            # Simulate incorrect OTP
            mock_redis.get.return_value = b'654321'
            assert redis_db.verify_otp('party1', 'track1', '123456') is False

def test_generate_and_verify_form_otp():
    with patch('database.redis_db.redis_client') as mock_redis:
        with patch('database.redis_db.random.randint', return_value=654321):
            from database import redis_db
            otp = redis_db.generate_form_otp('formtrack1', 'party2')
            assert otp == '654321'
            mock_redis.setex.assert_called_with('otp:party2:formtrack1', redis_db.OTP_EXPIRY_SECONDS, '654321')
            # Simulate correct OTP in redis
            mock_redis.get.return_value = b'654321'
            assert redis_db.verify_form_otp('party2', 'formtrack1', '654321') is True
            mock_redis.delete.assert_called_with('otp:party2:formtrack1')
            # Simulate incorrect OTP
            mock_redis.get.return_value = b'000000'
            assert redis_db.verify_form_otp('party2', 'formtrack1', '654321') is False
