"""
RealTimeTransfer
================

Application Entry Point

Configures the FastAPI app and registers the global lifespan handler.

Python 3.13+
"""

from __future__ import annotations

from app.bootstrap.application import create_application

app = create_application()