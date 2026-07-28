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
# Heartbeat
# ==========================================================

@dataclass(slots=True, frozen=True)
class HeartbeatConfig:

    enabled: bool

    interval: int

    timeout: int

    max_missed_heartbeats: int


heartbeat_config = HeartbeatConfig(
    enabled=True,
    interval=settings.WS_HEARTBEAT_INTERVAL,
    timeout=settings.WS_PING_TIMEOUT,
    max_missed_heartbeats=3,
)


# ==========================================================
# ACK
# ==========================================================

@dataclass(slots=True, frozen=True)
class AckConfig:

    enabled: bool

    timeout: int

    resend_limit: int


ack_config = AckConfig(
    enabled=True,
    timeout=5,
    resend_limit=5,
)


# ==========================================================
# Retry
# ==========================================================

@dataclass(slots=True, frozen=True)
class RetryConfig:

    max_retry: int

    retry_delay: float

    exponential_backoff: bool


retry_config = RetryConfig(
    max_retry=5,
    retry_delay=1.5,
    exponential_backoff=True,
)