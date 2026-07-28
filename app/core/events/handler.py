from abc import ABC
from abc import abstractmethod

from app.core.events.base import Event


class EventHandler(
    ABC,
):

    @abstractmethod
    async def handle(

        self,

        event: Event,

    ) -> None:
        ...