"""
Farmer Exchange Repository

Bulk SQL for importing / exporting the farmers of one VLCC. Core statements
only — one statement per table per batch — because the import's speed is
bounded by SQLite itself (see .gsd/phases/2/RESEARCH.md) and ORM objects
would add ~15 % on top. Business rules are the farmer module's, re-stated
here for set-based execution.

Python 3.13+
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.administration.infrastructure.models import UserModel
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.farmer.infrastructure.models import FarmerModel

_FARMERS = FarmerModel.__table__
_USERS = UserModel.__table__
_ADDRESSES = AddressModel.__table__
_BANKS = BankAccountModel.__table__

# Export / existing-farmer columns, labelled with FARMER_SHEET keys
_SHEET_COLUMNS = (
    _FARMERS.c.farmer_code.label("farmer_code"),
    _FARMERS.c.milk_type.label("milk_type"),
    _FARMERS.c.assigned_chart_rank.label("assigned_chart_rank"),
    _FARMERS.c.sms_enabled.label("sms_enabled"),
    _FARMERS.c.is_active.label("is_active"),
    _USERS.c.name.label("name"),
    _USERS.c.mobile.label("mobile"),
    _USERS.c.email.label("email"),
    _ADDRESSES.c.line.label("address_line"),
    _ADDRESSES.c.city.label("city"),
    _ADDRESSES.c.state.label("state"),
    _ADDRESSES.c.pincode.label("pincode"),
    _BANKS.c.account_holder.label("account_holder"),
    _BANKS.c.bank_name.label("bank_name"),
    _BANKS.c.account_number.label("account_number"),
    _BANKS.c.ifsc_code.label("ifsc_code"),
    _BANKS.c.upi_id.label("upi_id"),
)


_IN_CHUNK = 900                     # below SQLite's bound-parameter limit


@dataclass(slots=True, frozen=True)
class ExistingFarmer:
    """A farmer already stored under a code in the target VLCC (deleted ones included)."""

    farmer_id: UUID
    user_id: UUID
    address_id: UUID | None         # the user's address row (addresses.user_id is UNIQUE)
    linked_address_id: UUID | None  # what farmer_master.address_id points to (may be stale / null)
    bank_account_id: UUID | None
    is_deleted: bool
    values: dict[str, Any]          # current values by FARMER_SHEET key


def _chunks(values: Sequence[Any]) -> Iterable[Sequence[Any]]:
    for start in range(0, len(values), _IN_CHUNK):
        yield values[start:start + _IN_CHUNK]


def _by_id_update(table):
    """UPDATE table SET <keys of each param dict> WHERE id = :b_id — one executemany per batch."""
    return table.update().where(table.c.id == bindparam("b_id"))


def _joined():
    return (
        _FARMERS
        .join(_USERS, _USERS.c.id == _FARMERS.c.user_id)
        .outerjoin(_ADDRESSES, _ADDRESSES.c.id == _FARMERS.c.address_id)
        .outerjoin(_BANKS, _BANKS.c.id == _FARMERS.c.bank_account_id)
    )


class FarmerExchangeRepository:

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # EXPORT
    # =========================================================

    async def count_export(self, vlcc_id: UUID) -> int:
        stmt = select(func.count()).select_from(_FARMERS).where(
            _FARMERS.c.vlcc_id == vlcc_id,
            _FARMERS.c.is_deleted.is_(False),
        )
        return int(await self._session.scalar(stmt) or 0)

    async def export_page(self, vlcc_id: UUID, after_code: str | None, limit: int) -> Sequence[Row]:
        """
        One keyset page in farmer_code order. (vlcc_id, farmer_code) is UNIQUE,
        so `farmer_code > :last` is an index range scan — no OFFSET, constant cost per page.
        """
        stmt = (
            select(*_SHEET_COLUMNS)
            .select_from(_joined())
            .where(
                _FARMERS.c.vlcc_id == vlcc_id,
                _FARMERS.c.is_deleted.is_(False),
            )
            .order_by(_FARMERS.c.farmer_code)
            .limit(limit)
        )
        if after_code is not None:
            stmt = stmt.where(_FARMERS.c.farmer_code > after_code)
        return (await self._session.execute(stmt)).all()

    # =========================================================
    # IMPORT — PRE-CHECKS (one indexed query each per batch)
    # =========================================================

    async def existing_by_codes(self, vlcc_id: UUID, codes: Sequence[str]) -> dict[str, ExistingFarmer]:
        found: dict[str, ExistingFarmer] = {}
        # Address by user (one per user, UNIQUE), so an address not linked on the farmer row is still found
        joined = (
            _FARMERS
            .join(_USERS, _USERS.c.id == _FARMERS.c.user_id)
            .outerjoin(_ADDRESSES, _ADDRESSES.c.user_id == _FARMERS.c.user_id)
            .outerjoin(_BANKS, _BANKS.c.id == _FARMERS.c.bank_account_id)
        )
        for chunk in _chunks(list(codes)):
            stmt = (
                select(
                    _FARMERS.c.id.label("farmer_id"),
                    _FARMERS.c.user_id.label("user_id"),
                    _ADDRESSES.c.id.label("address_id"),
                    _FARMERS.c.address_id.label("linked_address_id"),
                    _FARMERS.c.bank_account_id.label("bank_account_id"),
                    _FARMERS.c.is_deleted.label("is_deleted"),
                    *_SHEET_COLUMNS,
                )
                .select_from(joined)
                .where(_FARMERS.c.vlcc_id == vlcc_id, _FARMERS.c.farmer_code.in_(chunk))
            )
            for row in (await self._session.execute(stmt)).all():
                mapping = dict(row._mapping)
                found[mapping["farmer_code"]] = ExistingFarmer(
                    farmer_id=mapping.pop("farmer_id"),
                    user_id=mapping.pop("user_id"),
                    address_id=mapping.pop("address_id"),
                    linked_address_id=mapping.pop("linked_address_id"),
                    bank_account_id=mapping.pop("bank_account_id"),
                    is_deleted=bool(mapping.pop("is_deleted")),
                    values=mapping,
                )
        return found

    async def users_by_emails(self, lower_emails: Sequence[str]) -> dict[str, UUID]:
        """lower(email) -> user id, for every user (deleted ones included). Uses ix_users_email_lower."""
        found: dict[str, UUID] = {}
        email = func.lower(_USERS.c.email)
        for chunk in _chunks(list(lower_emails)):
            for value, user_id in (await self._session.execute(select(email, _USERS.c.id).where(email.in_(chunk)))).all():
                found[value] = user_id
        return found

    async def users_by_mobiles(self, mobiles: Sequence[str]) -> dict[str, UUID]:
        found: dict[str, UUID] = {}
        for chunk in _chunks(list(mobiles)):
            stmt = select(_USERS.c.mobile, _USERS.c.id).where(_USERS.c.mobile.in_(chunk))
            for value, user_id in (await self._session.execute(stmt)).all():
                found[value] = user_id
        return found

    # =========================================================
    # IMPORT — BULK WRITES (inside the caller's transaction)
    # =========================================================

    async def insert_many(
        self,
        *,
        users: list[dict],
        addresses: list[dict],
        banks: list[dict],
        farmers: list[dict],
    ) -> None:
        # Foreign-key order: users first, farmers last
        for table, rows in ((_USERS, users), (_ADDRESSES, addresses), (_BANKS, banks), (_FARMERS, farmers)):
            if rows:
                await self._session.execute(table.insert(), rows)

    async def update_many(
        self,
        *,
        users: list[dict],
        passwords: list[dict],
        addresses: list[dict],
        banks: list[dict],
        farmers: list[dict],
    ) -> None:
        """Each dict carries `b_id` (the row id) plus the columns to set; all dicts of a list share keys."""
        for table, rows in (
            (_USERS, users), (_USERS, passwords), (_ADDRESSES, addresses), (_BANKS, banks), (_FARMERS, farmers),
        ):
            if rows:
                await self._session.execute(_by_id_update(table), rows)
