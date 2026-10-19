from datetime import UTC, datetime
from uuid import uuid4, UUID

from app.modules.common.bank.application.command import (
    CreateBankAccountCommand,
    UpdateBankAccountCommand,
    GetBankAccountQuery,
)

from app.modules.common.bank.domain.dto import BankAccountDto
from app.modules.common.bank.domain.entities import BankAccount
from app.modules.common.bank.domain.exceptions import BankAccountNotFoundException, InvalidBankAccountException
from app.modules.common.bank.domain.repository import IBankAccountRepository
from app.core.database.manager import DatabaseManager


class BankAccountHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self,
        database: DatabaseManager,
        repository: IBankAccountRepository,
    ) -> None:

        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateBankAccountCommand,
    ) -> BankAccountDto:

        self._validate(
            account_holder=command.account_holder,
            ifsc_code=command.ifsc_code,
            upi_id=command.upi_id,
        )

        now = datetime.now(UTC)

        account = BankAccount(
            id=uuid4(),

            user_id=command.user_id,

            account_holder=command.account_holder.strip(),

            bank_name=(
                command.bank_name.strip()
                if command.bank_name
                else None
            ),

            account_number=(
                command.account_number.strip()
                if command.account_number
                else None
            ),

            ifsc_code=(
                command.ifsc_code.upper().strip()
                if command.ifsc_code
                else None
            ),

            upi_id=(
                command.upi_id.strip()
                if command.upi_id
                else None
            ),

            created_at=now,
            updated_at=now,
        )

        async with self._database.transaction():

            await self._repository.create(
                account
            )

        return self._to_dto(account)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetBankAccountQuery,
    ) -> BankAccountDto:

        account = await self._repository.get_by_id(
            query.id
        )

        if account is None:
            raise BankAccountNotFoundException()

        return self._to_dto(account)

    # =========================================================
    # GET USER ACCOUNT
    # =========================================================

    async def get_by_user(
        self,
        user_id: UUID,
    ) -> BankAccountDto | None:

        account = (
            await self._repository
            .get_by_user_id(user_id)
        )

        if account is None:
            return None

        return self._to_dto(account)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateBankAccountCommand,
    ) -> BankAccountDto:

        self._validate(
            account_holder=command.account_holder,
            ifsc_code=command.ifsc_code,
            upi_id=command.upi_id,
        )

        async with self._database.transaction():

            account = (
                await self._repository
                .get_by_id(command.id)
            )

            if account is None:
                raise BankAccountNotFoundException()

            account.account_holder = (
                command.account_holder.strip()
            )

            account.bank_name = (
                command.bank_name.strip()
                if command.bank_name
                else None
            )

            account.account_number = (
                command.account_number.strip()
                if command.account_number
                else None
            )

            account.ifsc_code = (
                command.ifsc_code.upper().strip()
                if command.ifsc_code
                else None
            )

            account.upi_id = (
                command.upi_id.strip()
                if command.upi_id
                else None
            )

            account.updated_at = datetime.now(UTC)

            await self._repository.update(
                account
            )

        return self._to_dto(account)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        account_id: UUID,
    ) -> None:

        async with self._database.transaction():

            exists = await self._repository.exists(
                account_id
            )

            if not exists:
                raise BankAccountNotFoundException()

            await self._repository.delete(
                account_id
            )

    # =========================================================
    # VALIDATION
    # =========================================================

    @staticmethod
    def _validate(
        account_holder: str,
        ifsc_code: str | None,
        upi_id: str | None,
    ) -> None:

        if not account_holder.strip():
            raise InvalidBankAccountException(
                "Account holder is required."
            )

        if len(account_holder.strip()) > 150:
            raise InvalidBankAccountException(
                "Account holder is too long."
            )

        if ifsc_code:

            ifsc = ifsc_code.strip().upper()

            if len(ifsc) != 11:
                raise InvalidBankAccountException(
                    "Invalid IFSC code."
                )

        if upi_id:

            if "@" not in upi_id:
                raise InvalidBankAccountException(
                    "Invalid UPI ID."
                )

    # =========================================================
    # DTO
    # =========================================================

    @staticmethod
    def _to_dto(
        account: BankAccount,
    ) -> BankAccountDto:

        return BankAccountDto(
            id=account.id,
            user_id=account.user_id,

            account_holder=account.account_holder,
            bank_name=account.bank_name,
            account_number=account.account_number,
            ifsc_code=account.ifsc_code,
            upi_id=account.upi_id,
        )