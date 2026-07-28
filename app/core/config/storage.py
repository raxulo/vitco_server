"""
RealTimeTransfer
================

Storage Configuration

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.config.base import BaseConfig


# ==========================================================
# Storage Driver
# ==========================================================

class StorageDriver(StrEnum):

    LOCAL = "local"

    MINIO = "minio"

    S3 = "s3"

    AZURE = "azure"

    GCS = "gcs"


# ==========================================================
# Chunk Upload
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class ChunkConfig(BaseConfig):
    """
    Chunk upload configuration.
    """

    enabled: bool = True

    chunk_size: int = 8 * 1024 * 1024      # 8 MB

    parallel_uploads: int = 4

    resume_supported: bool = True

    temp_directory: str = "temp"


# ==========================================================
# File Validation
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class ValidationConfig(BaseConfig):

    max_file_size: int = 5 * 1024 * 1024 * 1024   # 5 GB

    allowed_extensions: tuple[str, ...] = ()

    blocked_extensions: tuple[str, ...] = (
        ".exe",
        ".bat",
        ".cmd",
        ".msi",
    )

    verify_checksum: bool = True

    checksum_algorithm: str = "sha256"


# ==========================================================
# Encryption
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class EncryptionConfig(BaseConfig):

    enabled: bool = False

    algorithm: str = "AES256"

    key: str | None = None


# ==========================================================
# Local Storage
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class LocalStorageConfig(BaseConfig):

    root_directory: str = "storage"

    upload_directory: str = "uploads"

    download_directory: str = "downloads"

    temp_directory: str = "temp"


# ==========================================================
# S3 Compatible Storage
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class S3Config(BaseConfig):

    endpoint: str = ""

    bucket: str = ""

    access_key: str = ""

    secret_key: str = ""

    region: str = ""

    secure: bool = True


# ==========================================================
# Main Storage Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class StorageConfig(BaseConfig):

    driver: StorageDriver = StorageDriver.LOCAL

    local: LocalStorageConfig = LocalStorageConfig()

    s3: S3Config = S3Config()

    chunk: ChunkConfig = ChunkConfig()

    validation: ValidationConfig = ValidationConfig()

    encryption: EncryptionConfig = EncryptionConfig()

    generate_thumbnail: bool = False

    remove_partial_uploads: bool = True

    cleanup_interval: int = 300