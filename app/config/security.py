"""
RealTimeTransfer
================

Security Configuration

Contains security-related configuration only.

Python : 3.13
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import settings


# ==========================================================
# JWT
# ==========================================================

@dataclass(slots=True, frozen=True)
class JWTConfig:
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int


jwt_config = JWTConfig(
    secret_key=settings.SECRET_KEY,
    algorithm=settings.JWT_ALGORITHM,
    access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    refresh_token_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
)


# ==========================================================
# Password
# ==========================================================

@dataclass(slots=True, frozen=True)
class PasswordConfig:
    minimum_length: int


password_config = PasswordConfig(
    minimum_length=settings.PASSWORD_MIN_LENGTH,
)


# ==========================================================
# OTP
# ==========================================================

@dataclass(slots=True, frozen=True)
class OTPConfig:
    digits: int
    expire_seconds: int
    max_retry: int


otp_config = OTPConfig(
    digits=settings.OTP_LENGTH,
    expire_seconds=settings.OTP_EXPIRE_SECONDS,
    max_retry=settings.OTP_MAX_RETRY,
)


# ==========================================================
# Encryption
# ==========================================================

@dataclass(slots=True, frozen=True)
class EncryptionConfig:
    enabled: bool
    algorithm: str
    key_size: int


encryption_config = EncryptionConfig(
    enabled=settings.ENABLE_ENCRYPTION,
    algorithm="AES-256-GCM",
    key_size=32,
)


# ==========================================================
# CORS
# ==========================================================

@dataclass(slots=True, frozen=True)
class CORSConfig:
    enabled: bool
    allow_credentials: bool
    allow_methods: tuple[str, ...]
    allow_headers: tuple[str, ...]
    allow_origins: tuple[str, ...]


cors_config = CORSConfig(
    enabled=settings.ENABLE_CORS,
    allow_credentials=True,
    allow_methods=("*",),
    allow_headers=("*",),
    allow_origins=("*",),
)