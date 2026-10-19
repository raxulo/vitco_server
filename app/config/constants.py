"""
RealTimeTransfer
================

Application Constants

These values are NOT loaded from environment variables.

Python  : 3.13
"""

from zoneinfo import ZoneInfo

from enum import IntEnum, StrEnum

###############################################################################
# Application
###############################################################################

APP_AUTHOR = "RealTimeTransfer"

APP_COMPANY = "RealTimeTransfer"

DEFAULT_ENCODING = "utf-8"

from app.core.clock import (
    IST,
    TIMEZONE_NAME,
    TIMEZONE_LABEL,
    now_ist,
    now_naive_ist,
    today_ist,
    to_ist,
    to_naive_ist,
    day_bounds_ist,
    format_ist,
    get_ist_now,
)

DEFAULT_TIMEZONE = TIMEZONE_LABEL


###############################################################################
# API
###############################################################################

API_PREFIX = "/api"

API_VERSION = "v1"

API_V1_PREFIX = f"{API_PREFIX}/{API_VERSION}"

###############################################################################
# WebSocket
###############################################################################

WS_PREFIX = "/ws"

WS_TRANSFER_ENDPOINT = "/transfer"

WS_HEARTBEAT_ENDPOINT = "/heartbeat"

WS_PAIRING_ENDPOINT = "/pair"

###############################################################################
# Transfer
###############################################################################

KB = 1024

MB = 1024 * KB

GB = 1024 * MB

TB = 1024 * GB

DEFAULT_CHUNK_SIZE = 512 * KB

MIN_CHUNK_SIZE = 64 * KB

MAX_CHUNK_SIZE = 4 * MB

HEADER_SIZE = 64

MAX_PACKET_SIZE = MAX_CHUNK_SIZE + HEADER_SIZE

DEFAULT_BUFFER_SIZE = 4 * MB

###############################################################################
# File
###############################################################################

TEMP_EXTENSION = ".part"

RESUME_EXTENSION = ".resume"

CHECKSUM_EXTENSION = ".sha256"

###############################################################################
# Packet Protocol
###############################################################################

PROTOCOL_VERSION = 1

PACKET_MAGIC = b"RTTF"

PACKET_HEADER_SIZE = 64

###############################################################################
# Heartbeat
###############################################################################

DEFAULT_HEARTBEAT_INTERVAL = 15

DEFAULT_PING_TIMEOUT = 30

###############################################################################
# Retry
###############################################################################

MAX_RETRY_COUNT = 5

DEFAULT_RETRY_DELAY = 2

###############################################################################
# Queue
###############################################################################

DEFAULT_QUEUE_SIZE = 1000

DEFAULT_PACKET_QUEUE = 5000

###############################################################################
# Cache
###############################################################################

CACHE_PREFIX = "rtt"

###############################################################################
# Database
###############################################################################

SQLITE_BUSY_TIMEOUT = 30

###############################################################################
# OTP
###############################################################################

OTP_DIGITS = 6

OTP_CHARSET = "0123456789"

###############################################################################
# Authentication
###############################################################################

AUTHORIZATION_HEADER = "Authorization"

BEARER = "Bearer"

###############################################################################
# Content Types
###############################################################################

APPLICATION_JSON = "application/json"

APPLICATION_BINARY = "application/octet-stream"

TEXT_HTML = "text/html"

###############################################################################
# Compression
###############################################################################

ZSTD_LEVEL_FAST = 1

ZSTD_LEVEL_DEFAULT = 3

ZSTD_LEVEL_MAX = 22

###############################################################################
# Encryption
###############################################################################

AES_KEY_SIZE = 32

AES_NONCE_SIZE = 12

AES_TAG_SIZE = 16

###############################################################################
# Logging
###############################################################################

LOG_ROTATION = "100 MB"

LOG_RETENTION = "30 days"

###############################################################################
# Transfer Status
###############################################################################


class TransferStatus(StrEnum):
    CREATED = "created"
    PAIRED = "paired"
    WAITING = "waiting"
    STARTING = "starting"
    TRANSFERRING = "transferring"
    PAUSED = "paused"
    RESUMING = "resuming"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


###############################################################################
# Device Status
###############################################################################


class DeviceStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    PAIRING = "pairing"
    BUSY = "busy"


###############################################################################
# User Role
###############################################################################


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


###############################################################################
# Connection State
###############################################################################


class ConnectionState(StrEnum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


###############################################################################
# Packet Type
###############################################################################


class PacketType(IntEnum):
    CONTROL = 1
    FILE = 2
    ACK = 3
    HEARTBEAT = 4
    ERROR = 5


###############################################################################
# Transfer Direction
###############################################################################


class TransferDirection(StrEnum):
    SEND = "send"
    RECEIVE = "receive"