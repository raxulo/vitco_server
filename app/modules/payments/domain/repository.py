from app.modules.payments.domain.entities import PaymentPairBalance
from app.modules.payments.domain.entities import PaymentLedgerEntry
from abc import abstractmethod
from abc import ABC
from decimal import Decimal
from app.modules.payments.domain.entities import PaymentAccount
from uuid import UUID


class IPaymentAccountRepository(ABC):

    @abstractmethod
    async def get_for_update(
        self,
        user_id: UUID,
    ) -> PaymentAccount:
        ...

    @abstractmethod
    async def ensure(
        self,
        user_id: UUID,
    ) -> PaymentAccount:
        ...

    @abstractmethod
    async def update_balance(
        self,
        user_id: UUID,
        balance: Decimal,
        version: int,
    ) -> None:
        ...

class IPaymentLedgerRepository(ABC):

    @abstractmethod
    async def create(
        self,
        entity: PaymentLedgerEntry,
    ) -> None:
        ...

    @abstractmethod
    async def list_for_user(
        self,
        user_id: UUID,
        cursor: int | None,
        limit: int,
    ) -> list[PaymentLedgerEntry]:
        ...

    @abstractmethod
    async def list_between_users(
        self,
        user_a: UUID,
        user_b: UUID,
        cursor: int | None,
        limit: int,
    ) -> list[PaymentLedgerEntry]:
        ...


class IPaymentPairRepository(ABC):

    @abstractmethod
    async def get_for_update(
        self,
        low_user_id: UUID,
        high_user_id: UUID,
    ) -> PaymentPairBalance | None:
        ...

    @abstractmethod
    async def update(
        self,
        low_user_id: UUID,
        high_user_id: UUID,
        low_user_balance: Decimal,
    ) -> None:
        ...

    @abstractmethod
    async def get(
        self,
        low_user_id: UUID,
        high_user_id: UUID,
    ) -> PaymentPairBalance | None:
        ...