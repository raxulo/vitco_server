from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.masters.advanced.domain.entities import (
    AdvanceMaster,
    AdvancePayItem,
    AdvancePayment,
)


class IAdvanceRepository(ABC):

    @abstractmethod
    async def create(self, entity: AdvanceMaster) -> None:
        ...

    @abstractmethod
    async def update(self, entity: AdvanceMaster) -> None:
        ...

    @abstractmethod
    async def delete(self, id: UUID) -> None:
        ...

    @abstractmethod
    async def get_by_id(self, id: UUID) -> AdvanceMaster | None:
        ...

    @abstractmethod
    async def get_by_number(self, number: str) -> AdvanceMaster | None:
        ...

    @abstractmethod
    async def exists_number(self, number: str) -> bool:
        ...

    @abstractmethod
    async def get_items(self, advance_id: UUID) -> list[AdvanceItem]:
        ...

    @abstractmethod
    async def save_items(self, advance_id: UUID, items: list[AdvanceItem]) -> None:
        ...

    @abstractmethod
    async def get_payments(self, advance_id: UUID) -> list[AdvancePayment]:
        ...

    @abstractmethod
    async def save_payment(self, payment: AdvancePayment) -> None:
        ...

    @abstractmethod
    async def list(self, offset: int, limit: int) -> list[AdvanceMaster]:
        ...

    @abstractmethod
    async def search(self, keyword: str, offset: int, limit: int) -> list[AdvanceMaster]:
        ...

    @abstractmethod
    async def count(self) -> int:
        ...

    @abstractmethod
    async def count_search(self, keyword: str) -> int:
        ...
