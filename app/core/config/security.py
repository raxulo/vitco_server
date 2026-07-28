"""
RealTimeTransfer
================

Security Configuration

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.config.base import BaseConfig


# ==========================================================
# Password Algorithm
# ==========================================================

class PasswordAlgorithm(StrEnum):

    ARGON2ID = "argon2id"

    BCRYPT = "bcrypt"


# ==========================================================
# JWT Algorithm
# ==========================================================

class JWTAlgorithm(StrEnum):

    HS256 = "HS256"

    HS384 = "HS384"

    HS512 = "HS512"

    RS256 = "RS256"


# ==========================================================
# Password Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class PasswordConfig(BaseConfig):

    algorithm: PasswordAlgorithm = PasswordAlgorithm.ARGON2ID

    min_length: int = 8

    max_length: int = 128

    require_uppercase: bool = True

    require_lowercase: bool = True

    require_number: bool = True

    require_special: bool = True


# ==========================================================
# JWT Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class JWTConfig(BaseConfig):

    algorithm: JWTAlgorithm = JWTAlgorithm.HS256

    secret_key: str = "CHANGE_ME"

    issuer: str = "RealTimeTransfer"

    audience: str = "RealTimeTransfer"

    access_token_expire: int = 900

    refresh_token_expire: int = 604800

    clock_skew: int = 30


# ==========================================================
# OTP Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class OTPConfig(BaseConfig):

    length: int = 6

    expiry: int = 300

    max_attempts: int = 5

    resend_interval: int = 30

    cleanup_interval: int = 60


# ==========================================================
# API Key Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class APIKeyConfig(BaseConfig):

    enabled: bool = False

    header_name: str = "X-API-Key"

    length: int = 64


# ==========================================================
# Session Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class SessionConfig(BaseConfig):

    timeout: int = 1800

    secure_cookie: bool = True

    http_only: bool = True

    same_site: str = "lax"


# ==========================================================
# Rate Limiter
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class RateLimitConfig(BaseConfig):

    enabled: bool = True

    requests: int = 100

    period: int = 60

    burst: int = 20


# ==========================================================
# Security Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class SecurityConfig(BaseConfig):

    password: PasswordConfig = PasswordConfig()

    jwt: JWTConfig = JWTConfig()

    otp: OTPConfig = OTPConfig()

    api_key: APIKeyConfig = APIKeyConfig()

    session: SessionConfig = SessionConfig()

    rate_limit: RateLimitConfig = RateLimitConfig()