"""
RealTimeTransfer
================

WebSocket Configuration

Production-ready WebSocket configuration.

Python : 3.13
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import settings


# ==========================================================
# Connection
# ==========================================================

@dataclass(slots=True, frozen=True)
class ConnectionConfig:
    """
    WebSocket Connection Configuration
    """

    max_connections: int

    authentication_timeout: int

    handshake_timeout: int

    close_timeout: int


connection_config = ConnectionConfig(
    max_connections=settings.MAX_CONCURRENT_CONNECTIONS,
    authentication_timeout=10,
    handshake_timeout=10,
    close_timeout=5,
)


# ==========================================================
# Binary Packet
# ==========================================================

@dataclass(slots=True, frozen=True)
class BinaryConfig:

    binary_only: bool

    max_frame_size: int

    fragmented_frames: bool


binary_config = BinaryConfig(
    binary_only=True,
    max_frame_size=settings.WS_MAX_MESSAGE_SIZE,
    fragmented_frames=True,
)


# ==========================================================
# Queue
# ==========================================================

@dataclass(slots=True, frozen=True)
class QueueConfig:

    receive_queue_size: int

    send_queue_size: int

    dispatcher_workers: int


queue_config = QueueConfig(
    receive_queue_size=2000,
    send_queue_size=2000,
    dispatcher_workers=8,
)


# ==========================================================
# Backpressure
# ==========================================================

@dataclass(slots=True, frozen=True)
class BackpressureConfig:

    enabled: bool

    max_pending_packets: int

    drop_when_full: bool


backpressure_config = BackpressureConfig(
    enabled=True,
    max_pending_packets=500,
    drop_when_full=False,
)


# ==========================================================
# Broadcast
# ==========================================================

@dataclass(slots=True, frozen=True)
class BroadcastConfig:

    enabled: bool

    batch_size: int

    flush_interval_ms: int


broadcast_config = BroadcastConfig(
    enabled=True,
    batch_size=128,
    flush_interval_ms=5,
)


# ==========================================================
# Rate Limiting
# ==========================================================

@dataclass(slots=True, frozen=True)
class RateLimitConfig:

    enabled: bool

    packets_per_second: int

    bytes_per_second: int


rate_limit_config = RateLimitConfig(
    enabled=True,
    packets_per_second=10000,
    bytes_per_second=100 * 1024 * 1024,
)


# ==========================================================
# Statistics
# ==========================================================

@dataclass(slots=True, frozen=True)
class StatisticsConfig:

    enabled: bool

    collect_interval: int


statistics_config = StatisticsConfig(
    enabled=True,
    collect_interval=5,
)