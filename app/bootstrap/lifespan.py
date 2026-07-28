"""
RealTimeTransfer
================

Application Lifespan

Enterprise Startup / Shutdown

Python 3.13
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.logger import logger
from app.core.database import database


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    """
    Enterprise application lifecycle.

    Startup Order

    Logger

    Database

    Redis

    Storage

    Queue

    Transfer Engine

    WebSocket

    Shutdown Order

    Reverse Startup Order
    """

    logger.info("Application starting...")

    await database.startup()

    logger.success("Database initialized.")

    try:

        yield

    finally:

        logger.info("Application shutting down...")

        await database.shutdown()

        logger.success("Database closed.")