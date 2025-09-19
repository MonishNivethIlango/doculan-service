from fastapi import HTTPException, status
import logging


class OTPException(Exception):
    """Base exception for OTP errors."""

class InvalidOTPException(OTPException):
    """Raised when OTP is invalid."""

class ExpiredOTPException(OTPException):
    """Raised when OTP is expired or missing."""