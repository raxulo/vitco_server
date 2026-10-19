"""
RealTimeTransfer
================

Enterprise Database Injection Dependencies

FastAPI Dependencies for database sessions, unit of work, and repositories.

Python 3.13+
"""
from __future__ import annotations

from typing import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import database, UnitOfWork
from app.core.database.session_context import SessionContext
from app.modules.auth.application.handler import LoginHandler


async def get_db_session() -> AsyncSession:
    """
    FastAPI dependency that returns the active request-scoped database session.
    """
    return SessionContext.get()


async def get_unit_of_work() -> AsyncIterator[UnitOfWork]:
    """
    FastAPI dependency that returns a UnitOfWork instance.
    """
    uow = UnitOfWork(database.transactions)
    yield uow


async def get_login_handler(request: Request) -> LoginHandler:
    return request.app.state.application.login_handler


# class GetHandler:
    
#     @staticmethod
#     def login_handler(request: Request) -> LoginHandler:
#         return request.app.state.application.login_handler

#     @staticmethod
#     def register_handler(request: Request):
#         return request.app.state.application.register_handler

#     @staticmethod
#     def health_check_handler(request: Request):
#         return request.app.state.application.health_check_handler