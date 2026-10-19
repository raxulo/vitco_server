"""
RealTimeTransfer
================

Filesystem Configuration

This module defines storage locations and filesystem policies.

Python : 3.13
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config.settings import settings


# ==========================================================
# Storage Paths
# ==========================================================

@dataclass(slots=True, frozen=True)
class StorageConfig:
    """
    Root storage directories.
    """

    root: Path

    temp: Path

    uploads: Path

    downloads: Path

    chunks: Path

    database: Path

    logs: Path

    media: Path


storage_config = StorageConfig(
    root=settings.STORAGE_PATH,
    temp=settings.TEMP_PATH,
    uploads=settings.UPLOAD_PATH,
    downloads=settings.DOWNLOAD_PATH,
    chunks=settings.CHUNK_PATH,
    database=settings.database_file.parent,
    logs=settings.LOG_PATH,
    media=settings.MEDIA_PATH,
)


# ==========================================================
# File Policy
# ==========================================================

@dataclass(slots=True, frozen=True)
class FilePolicyConfig:
    """
    File handling policy.
    """

    overwrite_existing: bool

    create_directories: bool

    preserve_extension: bool

    auto_cleanup_temp: bool

    cleanup_after_hours: int


file_policy_config = FilePolicyConfig(
    overwrite_existing=False,
    create_directories=True,
    preserve_extension=True,
    auto_cleanup_temp=True,
    cleanup_after_hours=24,
)


# ==========================================================
# Chunk Storage
# ==========================================================

@dataclass(slots=True, frozen=True)
class ChunkStorageConfig:

    extension: str

    directory_depth: int

    use_subdirectories: bool


chunk_storage_config = ChunkStorageConfig(
    extension=".chunk",
    directory_depth=2,
    use_subdirectories=True,
)


# ==========================================================
# Resume Storage
# ==========================================================

@dataclass(slots=True, frozen=True)
class ResumeStorageConfig:

    extension: str

    save_metadata: bool

    verify_on_resume: bool


resume_storage_config = ResumeStorageConfig(
    extension=".resume",
    save_metadata=True,
    verify_on_resume=True,
)


# ==========================================================
# File Validation
# ==========================================================

@dataclass(slots=True, frozen=True)
class ValidationConfig:

    validate_filename: bool

    validate_extension: bool

    validate_path_traversal: bool

    sanitize_filename: bool


validation_config = ValidationConfig(
    validate_filename=True,
    validate_extension=True,
    validate_path_traversal=True,
    sanitize_filename=True,
)


# ==========================================================
# Buffer Pool
# ==========================================================

@dataclass(slots=True, frozen=True)
class BufferPoolConfig:

    enabled: bool

    pool_size: int

    buffer_size: int


buffer_pool_config = BufferPoolConfig(
    enabled=True,
    pool_size=256,
    buffer_size=4 * 1024 * 1024,
)