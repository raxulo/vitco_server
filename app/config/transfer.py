"""
RealTimeTransfer
================

Transfer Engine Configuration

This module contains all high-performance transfer settings.

Python : 3.13
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import settings


# ==========================================================
# Chunk Configuration
# ==========================================================

@dataclass(slots=True, frozen=True)
class ChunkConfig:
    """
    File Chunk Configuration
    """

    default_size: int

    minimum_size: int

    maximum_size: int

    adaptive_chunk: bool


chunk_config = ChunkConfig(
    default_size=settings.CHUNK_SIZE,
    minimum_size=64 * 1024,
    maximum_size=4 * 1024 * 1024,
    adaptive_chunk=True,
)


# ==========================================================
# Buffer Configuration
# ==========================================================

@dataclass(slots=True, frozen=True)
class BufferConfig:

    read_buffer: int

    write_buffer: int

    socket_buffer: int

    zero_copy: bool


buffer_config = BufferConfig(
    read_buffer=4 * 1024 * 1024,
    write_buffer=4 * 1024 * 1024,
    socket_buffer=8 * 1024 * 1024,
    zero_copy=True,
)


# ==========================================================
# Resume Configuration
# ==========================================================

@dataclass(slots=True, frozen=True)
class ResumeConfig:

    enabled: bool

    save_interval: int

    checkpoint_size: int


resume_config = ResumeConfig(
    enabled=True,
    save_interval=5,
    checkpoint_size=20,
)


# ==========================================================
# Compression
# ==========================================================

@dataclass(slots=True, frozen=True)
class CompressionConfig:

    enabled: bool

    level: int

    minimum_file_size: int


compression_config = CompressionConfig(
    enabled=settings.ENABLE_COMPRESSION,
    level=settings.COMPRESSION_LEVEL,
    minimum_file_size=1024 * 1024,
)


# ==========================================================
# Encryption
# ==========================================================

@dataclass(slots=True, frozen=True)
class EncryptionConfig:

    enabled: bool

    algorithm: str

    key_length: int


encryption_config = EncryptionConfig(
    enabled=settings.ENABLE_ENCRYPTION,
    algorithm="AES-256-GCM",
    key_length=32,
)


# ==========================================================
# Parallel Transfer
# ==========================================================

@dataclass(slots=True, frozen=True)
class ParallelTransferConfig:

    max_parallel_files: int

    max_parallel_chunks: int

    worker_count: int


parallel_transfer_config = ParallelTransferConfig(
    max_parallel_files=5,
    max_parallel_chunks=8,
    worker_count=8,
)


# ==========================================================
# Flow Control
# ==========================================================

@dataclass(slots=True, frozen=True)
class FlowControlConfig:

    enabled: bool

    queue_size: int

    backpressure: bool


flow_control_config = FlowControlConfig(
    enabled=True,
    queue_size=1000,
    backpressure=True,
)