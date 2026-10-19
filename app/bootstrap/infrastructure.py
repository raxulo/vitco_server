"""
RealTimeTransfer
================

Infrastructure Configuration

Registers application infrastructure.

Python 3.13+
"""

from app.core.resources import resource_manager
from app.core.config import config
from app.core.database.factory import DatabaseFactory
from app.core.container.container import ServiceContainer

from app.bootstrap.state import ApplicationState

from app.core.cache import cache

from app.core.events.registry import EventRegistry
from app.core.events.dispatcher import EventDispatcher
from app.core.events.bus import EventBus

from app.core.database.unit_of_work import UnitOfWork


class InfrastructureConfigurator:
    """
    Configure application infrastructure.

    Responsibilities
    ----------------
    ✔ Database
    ✔ Cache
    ✔ EventBus
    ✔ UnitOfWork
    ✔ Lifecycle Registration

    Does NOT register:

    ✘ Handlers
    ✘ Services
    ✘ Repositories
    ✘ Modules
    """

    __slots__ = ()

    @classmethod
    def configure(
        cls,
        container: ServiceContainer,
    ) -> None:

        database = DatabaseFactory(
            config.database,
        ).create()

        container.database = database

        resource_manager.register(database)

        # --------------------------------------------------
        # Core Infrastructure
        # --------------------------------------------------

        container.cache = cache

        # resource_manager.register(database)

        if cache is not None:
            resource_manager.register(cache)

        # --------------------------------------------------
        # Event System
        # --------------------------------------------------

        registry = EventRegistry()

        dispatcher = EventDispatcher(
            container,
            registry,
        )

        bus = EventBus(
            dispatcher,
        )

        # container.event_registry = registry
        # container.event_dispatcher = dispatcher
        container.event_bus = bus

        # --------------------------------------------------
        # Unit Of Work
        # --------------------------------------------------

        # container.unit_of_work = UnitOfWork(
        #     database,
        # )

        # --------------------------------------------------
        # Freeze Container
        # --------------------------------------------------

