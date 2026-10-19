"""
RealTimeTransfer
================

Enterprise Event Dispatcher

Python 3.13+
"""

from __future__ import annotations

from typing import Callable, Awaitable, Any
import asyncio
import time
from dataclasses import dataclass, field

from app.core.container.container import ServiceContainer
from app.core.events.base import Event
from app.core.events.middleware import EventMiddleware
from app.core.events.registry import EventRegistry
from app.core.logging.logger import logger


@dataclass(slots=True)
class DispatchResult:
    """
    Result of a dispatch operation.
    """

    event: Event
    success: bool
    duration: float
    handlers: int
    exceptions: list[Exception] = field(default_factory=list)


class EventDispatcher:
    """
    Enterprise Event Dispatcher with Middleware Pipeline,
    Throttling Semaphore, and Background Execution.
    """

    __slots__ = (
        "_container",
        "_registry",
        "_middlewares",
        "_semaphore",
        "_pipelines",
    )

    def __init__(
        self,
        container: ServiceContainer,
        registry: EventRegistry,
        middlewares: list[EventMiddleware] | None = None,
        max_concurrency: int = 100,
    ) -> None:
        self._container = container
        self._registry = registry
        self._middlewares = middlewares or []
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._pipelines: dict[type, Callable[[Event], Awaitable[None]]] = {}

    async def dispatch(self, event: Event) -> DispatchResult:
        """
        Dispatches the event to all registered handlers through the middleware pipeline.
        """
        started = time.perf_counter()
        exceptions: list[Exception] = []
        handler_classes = self._registry.handlers(type(event))

        if not handler_classes:
            return DispatchResult(event=event, success=True, duration=0.0, handlers=0)

        sync_tasks = []

        for handler_cls in handler_classes:
            # Retrieve or compile the middleware pipeline for this handler class
            pipeline = self._pipelines.get(handler_cls)
            if pipeline is None:
                async def execute_handler(e: Event, h_cls=handler_cls) -> None:
                    async with self._semaphore:
                        instance = self._container.resolve(h_cls)
                        await instance.handle(e)

                pipeline = execute_handler
                for middleware in reversed(self._middlewares):
                    def make_middleware_step(mw: EventMiddleware, next_step: Callable[[Event], Any]):
                        async def invoke_mw(ev: Event) -> None:
                            await mw.invoke(ev, next_step)
                        return invoke_mw
                    pipeline = make_middleware_step(middleware, pipeline)
                self._pipelines[handler_cls] = pipeline

            # Check if handler should run out-of-band in background
            is_async = getattr(handler_cls, "async_run", False)
            if is_async:
                # Start as background fire-and-forget task
                async def run_in_background(pipe=pipeline, ev=event, h_cls=handler_cls) -> None:
                    try:
                        await pipe(ev)
                    except Exception as exc:
                        logger.error(
                            "Background event handler %s failed: %s",
                            h_cls.__name__,
                            str(exc),
                        )
                asyncio.create_task(run_in_background())
            else:
                # Run concurrently as part of dispatch blocking context
                sync_tasks.append(pipeline(event))

        if sync_tasks:
            results = await asyncio.gather(*sync_tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    exceptions.append(res)

        return DispatchResult(
            event=event,
            success=not exceptions,
            duration=time.perf_counter() - started,
            handlers=len(handler_classes),
            exceptions=exceptions,
        )