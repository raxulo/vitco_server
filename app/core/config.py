"""
RealTimeTransfer
================

Enterprise Configuration Provider

Author : Rahul Baghel
Python : 3.13
"""

from __future__ import annotations

from functools import cached_property

from app.config.settings import settings
from app.config.database import database_config
from app.config.logging import LOGGER_CONFIG
from app.config.security import (
    jwt_config,
    password_config,
    otp_config,
    encryption_config,
    cors_config,
)
from app.config.transfer import (
    chunk_config,
    buffer_config,
    resume_config,
    compression_config,
    parallel_transfer_config,
    flow_control_config,
)
from app.config.network import (
    retry_config,
    ack_config,
    heartbeat_config,
)
from app.config.websocket import (
    connection_config,
    binary_config,
    queue_config,
    backpressure_config,
    broadcast_config,
    rate_limit_config,
    statistics_config,
)
from app.config.filesystem import (
    storage_config,
    file_policy_config,
    chunk_storage_config,
    resume_storage_config,
    validation_config,
    buffer_pool_config,
)


class ConfigProvider:
    """
    Enterprise Configuration Provider.

    Lazy loaded.
    Singleton.
    Read Only.
    """

    @cached_property
    def settings(self):
        return settings

    @cached_property
    def database(self):
        return database_config

    @cached_property
    def logging(self):
        return LOGGER_CONFIG

    @cached_property
    def jwt(self):
        return jwt_config

    @cached_property
    def password(self):
        return password_config

    @cached_property
    def otp(self):
        return otp_config

    @cached_property
    def encryption(self):
        return encryption_config

    @cached_property
    def cors(self):
        return cors_config

    @cached_property
    def chunk(self):
        return chunk_config

    @cached_property
    def buffer(self):
        return buffer_config

    @cached_property
    def resume(self):
        return resume_config

    @cached_property
    def compression(self):
        return compression_config

    @cached_property
    def retry(self):
        return retry_config

    @cached_property
    def ack(self):
        return ack_config

    @cached_property
    def heartbeat(self):
        return heartbeat_config

    @cached_property
    def parallel(self):
        return parallel_transfer_config

    @cached_property
    def flow_control(self):
        return flow_control_config

    @cached_property
    def websocket(self):
        return connection_config

    @cached_property
    def websocket_binary(self):
        return binary_config

    @cached_property
    def websocket_queue(self):
        return queue_config

    @cached_property
    def websocket_backpressure(self):
        return backpressure_config

    @cached_property
    def websocket_broadcast(self):
        return broadcast_config

    @cached_property
    def websocket_rate_limit(self):
        return rate_limit_config

    @cached_property
    def websocket_statistics(self):
        return statistics_config

    @cached_property
    def storage(self):
        return storage_config

    @cached_property
    def filesystem(self):
        return file_policy_config

    @cached_property
    def validation(self):
        return validation_config

    @cached_property
    def chunk_storage(self):
        return chunk_storage_config

    @cached_property
    def resume_storage(self):
        return resume_storage_config

    @cached_property
    def buffer_pool(self):
        return buffer_pool_config


config = ConfigProvider()