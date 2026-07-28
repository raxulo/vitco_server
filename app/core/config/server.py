"""
RealTimeTransfer
================

Server Configuration

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.config.base import BaseConfig


# ==========================================================
# Environment
# ==========================================================

class Environment(StrEnum):

    DEVELOPMENT = "development"

    TESTING = "testing"

    STAGING = "staging"

    PRODUCTION = "production"


# ==========================================================
# HTTP Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class HTTPConfig(BaseConfig):
    """
    HTTP server configuration.
    """

    host: str = "0.0.0.0"

    port: int = 8000

    workers: int = 4

    backlog: int = 2048

    keep_alive: int = 5

    limit_concurrency: int | None = None

    limit_max_requests: int | None = None

    proxy_headers: bool = True

    forwarded_allow_ips: str = "*"


# ==========================================================
# CORS
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class CORSConfig(BaseConfig):

    enabled: bool = True

    allow_origins: tuple[str, ...] = ("*",)

    allow_methods: tuple[str, ...] = ("*",)

    allow_headers: tuple[str, ...] = ("*",)

    allow_credentials: bool = True

    expose_headers: tuple[str, ...] = ()

    max_age: int = 3600


# ==========================================================
# Compression
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class CompressionConfig(BaseConfig):

    enabled: bool = True

    minimum_size: int = 1024

    level: int = 6


# ==========================================================
# Trusted Hosts
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class TrustedHostConfig(BaseConfig):

    enabled: bool = False

    hosts: tuple[str, ...] = ("*",)


# ==========================================================
# Main Server Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class ServerConfig(BaseConfig):
    """
    Enterprise Server Configuration
    """

    app_name: str = "RealTimeTransfer"

    version: str = "1.0.0"

    environment: Environment = Environment.DEVELOPMENT

    debug: bool = False

    http: HTTPConfig = HTTPConfig()

    cors: CORSConfig = CORSConfig()

    compression: CompressionConfig = CompressionConfig()

    trusted_hosts: TrustedHostConfig = TrustedHostConfig()

    docs_enabled: bool = True

    openapi_enabled: bool = True

    lifespan_enabled: bool = True