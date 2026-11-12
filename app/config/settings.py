"""
RealTimeTransfer
----------------

Application Configuration

Author  : RealTimeTransfer
Python  : 3.13
"""

from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import sys


def _resolve_base_dir() -> Path:
    """
    Folder that holds the app's data: .env, storage/, logs/ and the SQLite DB.

    - Normal run: the project root (two levels above this file).
    - PyInstaller single-file build (``sys.frozen``): the folder that contains
      the executable, so data lives next to the binary and survives restarts
      instead of being written into the temporary unpack directory and lost.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


BASE_DIR = _resolve_base_dir()

class Settings(BaseSettings):
    """
    Global Application Settings

    All configuration values are loaded from environment variables.
    """

    ADMIN_NAME: str
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str

    # `.env` is the shared template (tracked, shipped by deploys). `.env.local` is per
    # machine (git-ignored, never deployed) and wins, e.g. the server's Postgres DATABASE_URL.
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR / ".env.local")),
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

    # PostgreSQL by default (DECISION-025); put the password in .env.
    # SQLite still works: sqlite+aiosqlite:///storage/database/realtime_transfer.db
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres@localhost:5432/quickyee"
    )

    DATABASE_ECHO: bool = False

    # Per process: the API and the exchange worker each hold a pool, so the
    # defaults (2 x 30) stay under PostgreSQL's 100 connections
    DATABASE_POOL_SIZE: int = 10

    DATABASE_MAX_OVERFLOW: int = 20

    # PostgreSQL only: longest a single statement may run; 0 turns the limit off
    DATABASE_STATEMENT_TIMEOUT_MS: int = 120_000
    

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

    MEDIA_PATH: Path = BASE_DIR / "storage" / "media"

    LOG_PATH: Path = BASE_DIR / "logs"

    # ==========================================================
    # Marketplace
    # ==========================================================

    MARKETPLACE_RATE_LIMIT_ENABLED: bool = True
    # The address customers use, such as https://shop.example.com. Search engine links use it.
    # Empty means the address of the current request.
    MARKETPLACE_PUBLIC_URL: str = ""

    # ==========================================================
    # Excel Data Exchange (import / export jobs)
    # ==========================================================

    EXCHANGE_PATH: Path = BASE_DIR / "storage" / "exchange"

    EXCHANGE_WORKER_ENABLED: bool = True

    EXCHANGE_MAX_CONCURRENT_JOBS: int = 2

    EXCHANGE_MAX_QUEUED_JOBS: int = 20

    EXCHANGE_MAX_UPLOAD_MB: int = 500

    EXCHANGE_UPLOAD_CHUNK_MB: int = 5

    EXCHANGE_MAX_UNCOMPRESSED_MB: int = 2048

    EXCHANGE_MAX_ROWS: int = 5_000_000

    EXCHANGE_MIN_FREE_DISK_MB: int = 1024

    EXCHANGE_FILE_TTL_HOURS: int = 24

    EXCHANGE_TX_BUDGET_MS: int = 250            # target duration of one worker write transaction

    EXCHANGE_BATCH_PAUSE_MS: int = 20           # pause between batches so API writers get the lock

    EXCHANGE_MAX_BATCH_SIZE: int = 500

    EXCHANGE_WORKER_MAX_MEMORY_MB: int = 1024

    EXCHANGE_HEARTBEAT_TIMEOUT_S: int = 120

    EXCHANGE_POLL_INTERVAL_MS: int = 1000

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