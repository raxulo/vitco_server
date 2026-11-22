# """
# RealTimeTransfer
# ================

# Bootstrap Module: Lifespan Management

# Coordinates async startup and shutdown hooks for databases and cache engines.

# Python 3.13+
# """

# from __future__ import annotations

# from contextlib import asynccontextmanager
# from typing import AsyncIterator

# from fastapi import FastAPI
# from app.bootstrap.state import app_state, ApplicationStatus
# from app.core.logger import logger


# @asynccontextmanager
# async def lifespan(app: FastAPI) -> AsyncIterator[None]:
#     """
#     FastAPI Lifespan context manager.
#     """
#     # 1. Startup hooks
#     app_state.transition_to(ApplicationStatus.STARTING)
    
#     try:
#         if app_state.database:
#             await app_state.database.startup()
#         if app_state.cache:
#             await app_state.cache.clear()
            
#         app_state.transition_to(ApplicationStatus.RUNNING)
#         logger.info("Application lifespan started successfully.")
#     except Exception as e:
#         logger.error(f"Application failed to startup: {e}. Executing rollback/shutdown.")
#         # Startup Rollback/Cleanup
#         if app_state.database:
#             try:
#                 await app_state.database.shutdown()
#             except Exception as shutdown_err:
#                 logger.error(f"Failed to shutdown database during startup rollback: {shutdown_err}")
#         app_state.transition_to(ApplicationStatus.STOPPED)
#         raise e

#     try:
#         yield
#     finally:
#         # 2. Shutdown hooks
#         app_state.transition_to(ApplicationStatus.STOPPING)
#         logger.info("Application lifespan shutting down...")
        
#         if app_state.database:
#             try:
#                 await app_state.database.shutdown()
#             except Exception as shutdown_err:
#                 logger.error(f"Error during database shutdown: {shutdown_err}")
                
#         app_state.transition_to(ApplicationStatus.STOPPED)
#         logger.info("Application shutdown completed.")


"""
RealTimeTransfer
================

Application Lifespan

Python 3.13+
"""

from app.modules.administration.application.handler import UserHandler
from app.modules.admin.application.handler import AdminHandler
from app.core.logging.logger import logger_manager
from app.modules.marketplace.infrastructure.seed import MarketplaceSeeder
from app.worker.supervisor import WorkerSupervisor
from app.modules.support.application.event_bus import EventBus
from app.modules.notification.application.worker import PushWorker

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap.state import (
    ApplicationState,
    ApplicationStatus,
)

from app.core.logging.logger import logger
from app.core.resources import resource_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Enterprise application lifecycle.
    Responsible only for orchestrating application startup
    and shutdown.
    """

    state: ApplicationState = app.state.application

    logger.info("Starting application...")

    state.set_status(ApplicationStatus.STARTING)

    try:
        logger_manager.startup()

        await resource_manager.startup()
        await state.container.database.startup()
    
        state.set_status(ApplicationStatus.RUNNING)

        seeder = state.container.resolve(UserHandler)
        async with state.container.database.transaction():
            await seeder.create_super_admin()

        # A store problem must never keep the dairy platform from starting
        try:
            await state.container.resolve(MarketplaceSeeder).run()
        except Exception:
            logger.exception("Marketplace starter data could not be created; the API keeps running.")

        # Excel import / export worker: a separate process, so a job can never slow down or crash the API
        exchange_supervisor = state.container.resolve(WorkerSupervisor)
        try:
            await exchange_supervisor.recover()
            await exchange_supervisor.start()
        except Exception:
            logger.exception("Excel exchange worker could not be started; the API keeps running.")

        # Support realtime: with no REDIS_URL, or when Redis is down, events stay inside this process
        try:
            await state.container.resolve(EventBus).start()
        except Exception:
            logger.exception("Support event bus could not be started; the API keeps running.")
        try:
            await state.container.resolve(PushWorker).start()
        except Exception:
            logger.exception("Push worker could not be started; the API keeps running.")

        logger.info("Application started.")

        yield

    finally:

        logger.info("Stopping application...")

        state.set_status(ApplicationStatus.STOPPING)
        try:
            await state.container.resolve(PushWorker).stop()
        except Exception:
            logger.exception("Push worker did not stop cleanly.")
        try:
            await state.container.resolve(EventBus).stop()
        except Exception:
            logger.exception("Support event bus did not stop cleanly.")
        try:
            await state.container.resolve(WorkerSupervisor).stop()
        except Exception:
            logger.exception("Excel exchange worker did not stop cleanly.")
        await state.container.database.shutdown()
        await resource_manager.shutdown()

        logger_manager.shutdown()
        
        state.set_status(ApplicationStatus.STOPPED)

        logger.info("Application stopped.")