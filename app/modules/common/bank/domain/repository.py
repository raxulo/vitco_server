from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.common.bank.domain.entities import BankAccount


class IBankAccountRepository(ABC):

    @abstractmethod
    async def create(
        self,
        account: BankAccount,
    ) -> None:
        ...

    @abstractmethod
    async def get_by_id(
        self,
        account_id: UUID,
    ) -> BankAccount | None:
        ...

    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> BankAccount | None:
        ...

    @abstractmethod
    async def update(
        self,
        account: BankAccount,
    ) -> None:
        ...

    @abstractmethod
    async def delete(
        self,
        account_id: UUID,
    ) -> None:
        ...

    @abstractmethod
    async def exists(
        self,
        account_id: UUID,
    ) -> bool:
        ...