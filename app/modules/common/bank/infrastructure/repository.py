from app.modules.common.bank.application.command import UpdateBankAccountCommand
from sqlalchemy import update
from uuid import UUID

from sqlalchemy import select

from app.core.database.manager import DatabaseManager

from app.modules.common.bank.domain.entities import BankAccount

from app.modules.common.bank.infrastructure.mapper import (
    BankAccountMapper,
)
from app.modules.common.bank.domain.repository import IBankAccountRepository

from app.modules.common.bank.infrastructure.models import (
    BankAccountModel,
)


class BankAccountRepository(
    IBankAccountRepository
):

    __slots__ = ("_database",)

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:

        self._database = database

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        account: BankAccount,
    ) -> None:

        model = BankAccountMapper.to_model(
            account
        )

        self._database.session.add(model)

    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        account_id: UUID,
    ) -> BankAccount | None:

        stmt = (
            select(BankAccountModel)
            .where(
                BankAccountModel.id == account_id,
            )
        )

        model = await self._database.session.scalar(
            stmt
        )

        if model is None:
            return None

        return BankAccountMapper.to_entity(model)

    # =========================================================
    # GET BY USER
    # =========================================================

    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> BankAccount | None:

        stmt = (
            select(BankAccountModel)
            .where(
                BankAccountModel.user_id == user_id,
            )
            .limit(1)
        )

        model = await self._database.session.scalar(
            stmt
        )

        if model is None:
            return None

        return BankAccountMapper.to_entity(model)

    # =========================================================
    # EXISTS
    # =========================================================

    async def exists(
        self,
        account_id: UUID,
    ) -> bool:

        stmt = (
            select(BankAccountModel.id)
            .where(
                BankAccountModel.id == account_id,
            )
            .limit(1)
        )

        result = await self._database.session.scalar(
            stmt
        )

        return result is not None

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        account: BankAccount,
    ) -> None:

        model = await self._database.session.get(
            BankAccountModel,
            account.id,
        )

        if model is None:
            return

        model.account_holder = (
            account.account_holder
        )

        model.bank_name = (
            account.bank_name
        )

        model.account_number = (
            account.account_number
        )

        model.ifsc_code = (
            account.ifsc_code
        )

        model.upi_id = (
            account.upi_id
        )

        model.updated_at = (
            account.updated_at
        )

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        account_id: UUID,
    ) -> None:

        model = await self._database.session.get(
            BankAccountModel,
            account_id,
        )

        if model is None:
            return

        await self._database.session.delete(
            model
        )

    async def update_bank_by_command(self, data: UpdateBankAccountCommand) -> BankAccount:
        stmt = (
            update(BankAccountModel)
            .where(BankAccountModel.id == data.id)
            .values(
                account_holder=data.account_holder,
                bank_name=data.bank_name,
                account_number=data.account_number,
                ifsc_code=data.ifsc_code,
                upi_id=data.upi_id,
            )
            .execution_options(synchronize_session="fetch")
            .returning(BankAccountModel)
        )

        model = await self._database.session.scalar(stmt)

        if model is None:
            raise ValueError("Bank account not found")

        return BankAccountMapper.to_entity(model)