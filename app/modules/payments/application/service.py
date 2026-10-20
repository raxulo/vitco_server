from app.modules.payments.application.dto import PaymentCollectionSummaryViaPeriodDto
from datetime import datetime
from app.core.database.manager import DatabaseManager
from app.modules.payments.application.command import PaymentPostingResult
from app.modules.payments.application.command import PostPaymentCommand
from app.modules.payments.infrastructure.repository import PaymentPairBalanceRepository
from app.modules.payments.infrastructure.repository import PaymentLedgerRepository
from app.modules.payments.infrastructure.repository import AccountBalanceRepository
from app.modules.payments.infrastructure.repository import PaymentTransferRepository

from decimal import Decimal
from uuid import UUID
from app.core.clock import now_naive_ist
from app.modules.payments.domain.exceptions import (
    InvalidPaymentAmount,
    SelfTransferNotAllowed,
    PaymentPostingFailed,
)


class PaymentPostingService:

    __slots__ = (
        "_database",
        "_custom_session",
    )

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:
        self._database = database
        self._custom_session = None

    async def __aenter__(self) -> "PaymentPostingService":
        self._custom_session = await self._database.get_async_session()
        return self

    async def __aexit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ) -> None:
        if self._custom_session:
            await self._custom_session.close()
            self._custom_session = None

    @property
    def _session(self):
        return self._custom_session or self._database.session

    @property
    def _transfer_repo(self) -> PaymentTransferRepository:
        return PaymentTransferRepository(self._session)

    @property
    def _account_repo(self) -> AccountBalanceRepository:
        return AccountBalanceRepository(self._session)

    @property
    def _ledger_repo(self) -> PaymentLedgerRepository:
        return PaymentLedgerRepository(self._session)

    @property
    def _pair_repo(self) -> PaymentPairBalanceRepository:
        return PaymentPairBalanceRepository(self._session)

    async def transaction_history_by_user(
        self,
        user_id: UUID,
        counterparty_id: UUID | None = None,
        search_q: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ):
        return await self._ledger_repo.get_user_history(
            user_id=user_id,
            counterparty_id=counterparty_id,
            search_q=search_q,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    async def get_user_balance(self, user_id: UUID) -> Decimal:
        return await self._account_repo.get_balance(user_id)

    async def get_user_outstanding(self, user_id: UUID) -> list:
        return await self._pair_repo.get_user_outstanding(user_id=user_id, include_zero=False)

    async def get_payment_summary_by_period(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> PaymentCollectionSummaryViaPeriodDto:
        return await self._ledger_repo.get_payment_summary_by_period(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
    
    async def post(
        self,
        command: PostPaymentCommand,
    ) -> PaymentPostingResult:

        # =====================================================
        # VALIDATION
        # =====================================================

        self._validate(command)

        async with self._database.transaction():

            if command.amount <= Decimal("0"):
                raise InvalidPaymentAmount()

            if command.sender_id == command.receiver_id:
                raise SelfTransferNotAllowed()

            # =====================================================
            # IDEMPOTENT TRANSFER
            # =====================================================

            transfer_id, created = (
                await self._transfer_repo.create_idempotent(
                    sender_id=command.sender_id,
                    receiver_id=command.receiver_id,
                    amount=command.amount,
                    source_type=command.source_type,
                    payment_method=command.payment_method,
                    idempotency_key=command.idempotency_key,
                    source_id=command.source_id,
                    reference=command.reference,
                    description=command.description,
                )
            )

            # =====================================================
            # DUPLICATE REQUEST
            # =====================================================

            if not created:
                return await self._build_existing_result(
                    transfer_id=transfer_id,
                )

            amount = command.amount

            # =====================================================
            # DETERMINISTIC ACCOUNT ORDER
            #
            # Prevents deadlocks:
            #
            # A -> B
            # B -> A
            #
            # Both transactions lock UUIDs in same order.
            # =====================================================

            first_user_id, second_user_id = sorted(
                (
                    command.sender_id,
                    command.receiver_id,
                )
            )

            # =====================================================
            # LOCK ACCOUNTS
            # =====================================================

            first_account = (
                await self._account_repo.get_for_update(
                    first_user_id,
                )
            )
            if first_account is None:
                await self._account_repo.create(first_user_id, Decimal("0.00"))
                first_account = (
                    await self._account_repo.get_for_update(
                        first_user_id,
                    )
                )

            second_account = (
                await self._account_repo.get_for_update(
                    second_user_id,
                )
            )
            if second_account is None:
                await self._account_repo.create(second_user_id, Decimal("0.00"))
                second_account = (
                    await self._account_repo.get_for_update(
                        second_user_id,
                    )
                )

            if first_account is None or second_account is None:
                raise PaymentPostingFailed()

            # =====================================================
            # CURRENT BALANCES
            # =====================================================

            if command.sender_id == first_user_id:

                sender_before = first_account[0]
                receiver_before = second_account[0]

            else:

                sender_before = second_account[0]
                receiver_before = first_account[0]

            # =====================================================
            # CALCULATE NEW BALANCES
            # =====================================================

            sender_after = sender_before - amount

            receiver_after = receiver_before + amount

            # =====================================================
            # ACCOUNT BALANCES
            # =====================================================

            if command.sender_id == first_user_id:

                first_after = sender_after
                second_after = receiver_after

            else:

                first_after = receiver_after
                second_after = sender_after

            # =====================================================
            # LEDGER
            # =====================================================

            sender_ledger_id, receiver_ledger_id = await self._ledger_repo.add_transfer_entries(
                transfer_id=transfer_id,
                sender_id=command.sender_id,
                receiver_id=command.receiver_id,
                amount=amount,
                sender_before=sender_before,
                sender_after=sender_after,
                receiver_before=receiver_before,
                receiver_after=receiver_after,
                created_at=now_naive_ist(),
            )

            # =====================================================
            # UPDATE ACCOUNT BALANCES
            # =====================================================

            await self._account_repo.apply_delta(
                user_id=first_user_id,
                delta=(
                    first_after - first_account[0]
                ),
                ledger_id=sender_ledger_id
                if first_user_id == command.sender_id
                else receiver_ledger_id,
            )

            await self._account_repo.apply_delta(
                user_id=second_user_id,
                delta=(
                    second_after - second_account[0]
                ),
                ledger_id=sender_ledger_id
                if second_user_id == command.sender_id
                else receiver_ledger_id,
            )

            # =====================================================
            # PAIR BALANCES
            # =====================================================

            (
                sender_pair_balance,
                receiver_pair_balance,
            ) = await self._pair_repo.apply_transfer(
                sender_id=command.sender_id,
                receiver_id=command.receiver_id,
                amount=amount,
                transfer_id=transfer_id,
            )

            # =====================================================
            # COMMIT
            #
            # IMPORTANT:
            # All repositories use SAME session.
            # =====================================================

            return PaymentPostingResult(
                transfer_id=transfer_id,
                created=True,
                sender_balance=sender_after,
                receiver_balance=receiver_after,
                sender_pair_balance=sender_pair_balance,
                receiver_pair_balance=receiver_pair_balance,
                sender_ledger_id=sender_ledger_id,
                receiver_ledger_id=receiver_ledger_id,
            )

    # async def post(
    #     self,
    #     command: CreatePaymentTransferCommand,
    # ):
    #     self._validate(command)

    #     # =====================================================
    #     # IDEMPOTENCY
    #     # =====================================================

    #     existing = await self._transfers.get_by_idempotency_key(
    #         command.idempotency_key
    #     )

    #     if existing is not None:
    #         return existing

    #     # =====================================================
    #     # DETERMINISTIC LOCK ORDER
    #     #
    #     # Prevents:
    #     #
    #     # A -> B
    #     # B -> A
    #     #
    #     # deadlock.
    #     # =====================================================

    #     first_user, second_user = sorted(
    #         (
    #             command.sender_id,
    #             command.receiver_id,
    #         )
    #     )

    #     async with self._session.begin():

    #         # =================================================
    #         # LOCK ACCOUNTS
    #         # =================================================

    #         first_account = (
    #             await self._accounts.get_for_update(
    #                 first_user
    #             )
    #         )

    #         second_account = (
    #             await self._accounts.get_for_update(
    #                 second_user
    #             )
    #         )

    #         if first_account is None:
    #             raise ValueError(
    #                 f"Account balance not found: {first_user}"
    #             )

    #         if second_account is None:
    #             raise ValueError(
    #                 f"Account balance not found: {second_user}"
    #             )

    #         accounts = {
    #             first_user: first_account,
    #             second_user: second_account,
    #         }

    #         sender_account = accounts[
    #             command.sender_id
    #         ]

    #         receiver_account = accounts[
    #             command.receiver_id
    #         ]

    #         # =================================================
    #         # BALANCE BEFORE
    #         # =================================================

    #         sender_before = sender_account.balance
    #         receiver_before = receiver_account.balance

    #         # =================================================
    #         # CREATE TRANSFER
    #         # =================================================

    #         transfer = await self._transfers.create_posted(
    #             sender_id=command.sender_id,
    #             receiver_id=command.receiver_id,
    #             amount=command.amount,
    #             source_type=command.source_type,
    #             payment_method=command.payment_method,
    #             source_id=command.source_id,
    #             idempotency_key=command.idempotency_key,
    #             reference=command.reference,
    #             description=command.description,
    #         )

    #         # =================================================
    #         # NEW BALANCES
    #         # =================================================

    #         sender_after = (
    #             sender_before - command.amount
    #         )

    #         receiver_after = (
    #             receiver_before + command.amount
    #         )

    #         # =================================================
    #         # LEDGER ENTRIES
    #         # =================================================

    #         sender_ledger = (
    #             self._ledger.build_entry(
    #                 transfer_id=transfer.id,
    #                 user_id=command.sender_id,
    #                 counterparty_id=command.receiver_id,
    #                 entry_type=LedgerEntryType.DEBIT,
    #                 amount=command.amount,
    #                 balance_before=sender_before,
    #                 balance_after=sender_after,
    #             )
    #         )

    #         receiver_ledger = (
    #             self._ledger.build_entry(
    #                 transfer_id=transfer.id,
    #                 user_id=command.receiver_id,
    #                 counterparty_id=command.sender_id,
    #                 entry_type=LedgerEntryType.CREDIT,
    #                 amount=command.amount,
    #                 balance_before=receiver_before,
    #                 balance_after=receiver_after,
    #             )
    #         )

    #         await self._ledger.add_many(
    #             [
    #                 sender_ledger,
    #                 receiver_ledger,
    #             ]
    #         )

    #         # =================================================
    #         # ACCOUNT BALANCES
    #         # =================================================

    #         await self._accounts.apply_delta(
    #             user_id=command.sender_id,
    #             delta=-command.amount,
    #             ledger_id=sender_ledger.id,
    #         )

    #         await self._accounts.apply_delta(
    #             user_id=command.receiver_id,
    #             delta=command.amount,
    #             ledger_id=receiver_ledger.id,
    #         )

    #         # =================================================
    #         # PAIR BALANCES
    #         #
    #         # sender -> receiver
    #         # decreases
    #         #
    #         # receiver -> sender
    #         # increases
    #         # =================================================

    #         await self._pairs.upsert_delta(
    #             user_id=command.sender_id,
    #             counterparty_id=command.receiver_id,
    #             delta=-command.amount,
    #             transfer_id=transfer.id,
    #         )

    #         await self._pairs.upsert_delta(
    #             user_id=command.receiver_id,
    #             counterparty_id=command.sender_id,
    #             delta=command.amount,
    #             transfer_id=transfer.id,
    #         )

    #         # =================================================
    #         # POSTED
    #         # =================================================

    #         await self._transfers.mark_posted(
    #             transfer.id
    #         )

    #         return transfer

    # # =========================================================
    # # VALIDATION
    # # =========================================================

    async def _build_existing_result(
        self,
        *,
        transfer_id: UUID,
    ) -> PaymentPostingResult:

        transfer = await self._transfer_repo.get_basic(
            transfer_id,
        )

        if transfer is None:
            raise PaymentPostingFailed()

        (
            sender_id,
            receiver_id,
            amount,
            status,
        ) = transfer

        sender_balance = (
            await self._account_repo.get_balance(
                sender_id,
            )
        )

        receiver_balance = (
            await self._account_repo.get_balance(
                receiver_id,
            )
        )

        sender_pair_balance = (
            await self._pair_repo.get(
                user_id=sender_id,
                counterparty_id=receiver_id,
            )
        )

        receiver_pair_balance = (
            await self._pair_repo.get(
                user_id=receiver_id,
                counterparty_id=sender_id,
            )
        )

        return PaymentPostingResult(
            transfer_id=transfer_id,
            created=False,
            sender_balance=sender_balance,
            receiver_balance=receiver_balance,
            sender_pair_balance=(
                sender_pair_balance
                or Decimal("0.00")
            ),
            receiver_pair_balance=(
                receiver_pair_balance
                or Decimal("0.00")
            ),
            sender_ledger_id=None,
            receiver_ledger_id=None,
        )

    @staticmethod
    def _validate(
        command: PostPaymentCommand,
    ) -> None:

        if command.sender_id == command.receiver_id:
            raise ValueError(
                "Sender and receiver must be different"
            )

        if command.amount <= Decimal("0"):
            raise ValueError(
                "Payment amount must be greater than zero"
            )

        if not command.idempotency_key:
            raise ValueError(
                "Idempotency key is required"
            )