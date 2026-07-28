"""
RealTimeTransfer
----------------

Application Configuration

Author  : RealTimeTransfer
Python  : 3.13
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Global Application Settings

    All configuration values are loaded from environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==========================================================
    # Application
    # ==========================================================

    APP_NAME: str = "RealTimeTransfer"

    APP_VERSION: str = "1.0.0"

    APP_DESCRIPTION: str = (
        "Distributed Enterprise Real-Time File Transfer Platform"
    )

    ENVIRONMENT: Literal[
        "development",
        "testing",
        "staging",
        "production",
    ] = "development"

    DEBUG: bool = True

    SECRET_KEY: str = Field(
        default="CHANGE_ME",
        min_length=32,
    )

    # ==========================================================
    # Server
    # ==========================================================

    HOST: str = "0.0.0.0"

    PORT: int = 8000

    WORKERS: int = 1

    RELOAD: bool = False

    # ==========================================================
    # Database
    # ==========================================================

    DATABASE_URL: str = (
        "sqlite+aiosqlite:///storage/database/realtime_transfer.db"
    )

    DATABASE_ECHO: bool = False

    DATABASE_POOL_SIZE: int = 20

    DATABASE_MAX_OVERFLOW: int = 50

    # ==========================================================
    # Transfer
    # ==========================================================

    MAX_FILE_SIZE: int = 1024 * 1024 * 1024 * 100      # 100 GB

    CHUNK_SIZE: int = 1024 * 512                        # 512 KB

    MAX_CONCURRENT_TRANSFERS: int = 100

    MAX_CONCURRENT_CONNECTIONS: int = 100000

    TRANSFER_TIMEOUT: int = 600

    ENABLE_RESUME: bool = True

    ENABLE_COMPRESSION: bool = True

    ENABLE_ENCRYPTION: bool = True

    # ==========================================================
    # WebSocket
    # ==========================================================

    WS_HEARTBEAT_INTERVAL: int = 15

    WS_MAX_MESSAGE_SIZE: int = 1024 * 1024

    WS_PING_TIMEOUT: int = 30

    # ==========================================================
    # OTP
    # ==========================================================

    OTP_LENGTH: int = 6

    OTP_EXPIRE_SECONDS: int = 300

    OTP_MAX_RETRY: int = 5

    # ==========================================================
    # JWT
    # ==========================================================

    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ==========================================================
    # Logging
    # ==========================================================

    LOG_LEVEL: Literal[
        "TRACE",
        "DEBUG",
        "INFO",
        "SUCCESS",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    LOG_FILE: str = "logs/application.log"

    # ==========================================================
    # Compression
    # ==========================================================

    COMPRESSION_LEVEL: int = 3

    # ==========================================================
    # Security
    # ==========================================================

    PASSWORD_MIN_LENGTH: int = 8

    ENABLE_CORS: bool = True

    # ==========================================================
    # Paths
    # ==========================================================

    STORAGE_PATH: Path = BASE_DIR / "storage"

    TEMP_PATH: Path = BASE_DIR / "storage" / "temp"

    UPLOAD_PATH: Path = BASE_DIR / "storage" / "uploads"

    DOWNLOAD_PATH: Path = BASE_DIR / "storage" / "downloads"

    CHUNK_PATH: Path = BASE_DIR / "storage" / "chunks"

    LOG_PATH: Path = BASE_DIR / "logs"

    # ==========================================================
    # Computed
    # ==========================================================

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @computed_field
    @property
    def database_file(self) -> Path:
        return BASE_DIR / "storage" / "database" / "realtime_transfer.db"


@lru_cache
def get_settings() -> Settings:
    """
    Cached Settings Instance

    Returns
    -------
    Settings
    """

    return Settings()


settings = get_settings()