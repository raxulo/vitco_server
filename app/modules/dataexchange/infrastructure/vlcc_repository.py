"""
VLCC Exchange Repository

Bulk SQL for importing and exporting the VLCCs of an owner (Admin, Sub Admin, MCC).
Uses SQLAlchemy Core statements for set-based performance without ORM overhead.

Python 3.13+
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, func, or_, select, tuple_
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.modules.administration.infrastructure.models import UserModel
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.common.milk_quality.infrastructure.models import MilkQualityConfigModel
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.vlcc.infrastructure.models import VlccModel

_VLCCS = VlccModel.__table__
_USERS = UserModel.__table__
_ADDRESSES = AddressModel.__table__
_BANKS = BankAccountModel.__table__
_SETTINGS = SettingsModel.__table__
_MILK = MilkQualityConfigModel.__table__

_SHEET_COLUMNS = (
    # VLCC Entity
    _VLCCS.c.vlcc_code.label("vlcc_code"),
    _VLCCS.c.uic_code.label("uic_code"),
    _VLCCS.c.name.label("vlcc_name"),
    _VLCCS.c.contact_person.label("contact_person"),
    _VLCCS.c.entry_mode.label("entry_mode"),
    _VLCCS.c.route_code.label("route_code"),
    _VLCCS.c.soc_percentage.label("soc_percentage"),
    _VLCCS.c.farmer_enabled.label("farmer_enabled"),
    _VLCCS.c.is_active.label("is_active"),
    _VLCCS.c.assigned_chart_rank.label("assigned_chart_rank"),
    # User
    _USERS.c.name.label("user_name"),
    _USERS.c.mobile.label("mobile"),
    _USERS.c.email.label("email"),
    # Address
    _ADDRESSES.c.line.label("address_line"),
    _ADDRESSES.c.city.label("city"),
    _ADDRESSES.c.state.label("state"),
    _ADDRESSES.c.pincode.label("pincode"),
    # Bank
    _BANKS.c.account_holder.label("account_holder"),
    _BANKS.c.bank_name.label("bank_name"),
    _BANKS.c.account_number.label("account_number"),
    _BANKS.c.ifsc_code.label("ifsc_code"),
    _BANKS.c.upi_id.label("upi_id"),
    # Settings
    _SETTINGS.c.analyzer_type.label("analyzer_type"),
    _SETTINGS.c.analyzer_collection_mode.label("analyzer_collection_mode"),
    _SETTINGS.c.weight_unit.label("weight_unit"),
    _SETTINGS.c.weight_collection_mode.label("weight_collection_mode"),
    _SETTINGS.c.auto_tare_enabled.label("auto_tare_enabled"),
    _SETTINGS.c.morning_collection_start.label("morning_collection_start"),
    _SETTINGS.c.morning_collection_end.label("morning_collection_end"),
    _SETTINGS.c.evening_collection_start.label("evening_collection_start"),
    _SETTINGS.c.evening_collection_end.label("evening_collection_end"),
    _SETTINGS.c.receipt_size.label("receipt_size"),
    _SETTINGS.c.printer_type.label("printer_type"),
    _SETTINGS.c.printer_enabled.label("printer_enabled"),
    _SETTINGS.c.supported_cattle_type.label("cattle_type"),
    # Milk Quality
    _MILK.c.cow_min_fat.label("cow_min_fat"),
    _MILK.c.cow_max_fat.label("cow_max_fat"),
    _MILK.c.cow_min_snf.label("cow_min_snf"),
    _MILK.c.cow_max_snf.label("cow_max_snf"),
    _MILK.c.buffalo_min_fat.label("buffalo_min_fat"),
    _MILK.c.buffalo_max_fat.label("buffalo_max_fat"),
    _MILK.c.buffalo_min_snf.label("buffalo_min_snf"),
    _MILK.c.buffalo_max_snf.label("buffalo_max_snf"),
)

_IN_CHUNK = 900


@dataclass(slots=True, frozen=True)
class ExistingVlcc:
    """A VLCC already stored under a code for the owner."""

    vlcc_id: UUID
    user_id: UUID
    address_id: UUID | None
    bank_account_id: UUID | None
    settings_id: UUID | None
    milk_quality_config_id: UUID | None
    is_deleted: bool
    values: dict[str, Any]


def _chunks(values: Sequence[Any]) -> Iterable[Sequence[Any]]:
    for start in range(0, len(values), _IN_CHUNK):
        yield values[start:start + _IN_CHUNK]


def _by_id_update(table):
    return table.update().where(table.c.id == bindparam("b_id"))


def _joined():
    return (
        _VLCCS
        .join(_USERS, _USERS.c.id == _VLCCS.c.user_id)
        .outerjoin(_ADDRESSES, _ADDRESSES.c.id == _VLCCS.c.address_id)
        .outerjoin(_BANKS, _BANKS.c.id == _VLCCS.c.bank_account_id)
        .outerjoin(_SETTINGS, _SETTINGS.c.id == _VLCCS.c.settings_id)
        .outerjoin(_MILK, _MILK.c.id == _VLCCS.c.milk_quality_config_id)
    )


class VlccExchangeRepository:

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # EXPORT
    # =========================================================

    async def count_export(self, owner_id: UUID) -> int:
        stmt = select(func.count()).select_from(_VLCCS).where(
            _VLCCS.c.created_by == owner_id,
            _VLCCS.c.is_deleted.is_(False),
        )
        return int(await self._session.scalar(stmt) or 0)

    async def export_page(
        self,
        owner_id: UUID,
        after: tuple[str, UUID] | None,
        limit: int,
    ) -> Sequence[Row]:
        """
        Keyset pagination by (vlcc_code, id) for stable, offset-free scanning.
        """
        stmt = (
            select(_VLCCS.c.id.label("vlcc_id"), *_SHEET_COLUMNS)
            .select_from(_joined())
            .where(
                _VLCCS.c.created_by == owner_id,
                _VLCCS.c.is_deleted.is_(False),
            )
            .order_by(_VLCCS.c.vlcc_code, _VLCCS.c.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(
                tuple_(_VLCCS.c.vlcc_code, _VLCCS.c.id) > after
            )
        return (await self._session.execute(stmt)).all()

    # =========================================================
    # IMPORT — PRE-CHECKS
    # =========================================================

    async def existing_by_codes(
        self,
        owner_id: UUID,
        codes: Sequence[str],
    ) -> dict[str, ExistingVlcc]:
        """Existing VLCCs owned by owner_id (soft-deleted included)."""
        found: dict[str, ExistingVlcc] = {}
        for chunk in _chunks(list(codes)):
            stmt = (
                select(
                    _VLCCS.c.id.label("vlcc_id"),
                    _VLCCS.c.user_id.label("user_id"),
                    _VLCCS.c.address_id.label("address_id"),
                    _VLCCS.c.bank_account_id.label("bank_account_id"),
                    _VLCCS.c.settings_id.label("settings_id"),
                    _VLCCS.c.milk_quality_config_id.label("milk_quality_config_id"),
                    _VLCCS.c.is_deleted.label("is_deleted"),
                    *_SHEET_COLUMNS,
                )
                .select_from(_joined())
                .where(
                    _VLCCS.c.created_by == owner_id,
                    _VLCCS.c.vlcc_code.in_(chunk),
                )
            )
            for row in (await self._session.execute(stmt)).all():
                mapping = dict(row._mapping)
                found[mapping["vlcc_code"]] = ExistingVlcc(
                    vlcc_id=mapping.pop("vlcc_id"),
                    user_id=mapping.pop("user_id"),
                    address_id=mapping.pop("address_id"),
                    bank_account_id=mapping.pop("bank_account_id"),
                    settings_id=mapping.pop("settings_id"),
                    milk_quality_config_id=mapping.pop("milk_quality_config_id"),
                    is_deleted=bool(mapping.pop("is_deleted")),
                    values=mapping,
                )
        return found

    async def code_conflicts_in_hierarchy(
        self,
        owner_user: Any,
        codes: Sequence[str],
        exclude_owner_id: UUID | None = None,
    ) -> set[str]:
        """
        Check if any codes conflict with VLCCs in the owner's hierarchy line (REQ-15),
        excluding records already owned by `exclude_owner_id` (which are updates).
        """
        conflicts: set[str] = set()
        conflict_condition = Hierarchy.code_conflict(owner_user, _VLCCS.c.created_by)
        for chunk in _chunks(list(codes)):
            stmt = (
                select(_VLCCS.c.vlcc_code)
                .where(
                    _VLCCS.c.vlcc_code.in_(chunk),
                    conflict_condition,
                )
            )
            if exclude_owner_id is not None:
                stmt = stmt.where(_VLCCS.c.created_by != exclude_owner_id)
            for (code,) in (await self._session.execute(stmt)).all():
                conflicts.add(code)
        return conflicts

    async def users_by_emails(self, lower_emails: Sequence[str]) -> dict[str, UUID]:
        found: dict[str, UUID] = {}
        email = func.lower(_USERS.c.email)
        for chunk in _chunks(list(lower_emails)):
            for value, user_id in (await self._session.execute(
                select(email, _USERS.c.id).where(email.in_(chunk))
            )).all():
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
    # IMPORT — BULK WRITES
    # =========================================================

    async def insert_many(
        self,
        *,
        users: list[dict],
        addresses: list[dict],
        banks: list[dict],
        settings: list[dict],
        milk_configs: list[dict],
        vlccs: list[dict],
    ) -> None:
        """Insert records in foreign-key order: users, rels, then vlccs."""
        for table, rows in (
            (_USERS, users),
            (_ADDRESSES, addresses),
            (_BANKS, banks),
            (_SETTINGS, settings),
            (_MILK, milk_configs),
            (_VLCCS, vlccs),
        ):
            if rows:
                await self._session.execute(table.insert(), rows)

    async def update_many(
        self,
        *,
        users: list[dict],
        passwords: list[dict],
        addresses: list[dict],
        banks: list[dict],
        settings: list[dict],
        milk_configs: list[dict],
        vlccs: list[dict],
    ) -> None:
        """Batch update by ID."""
        for table, rows in (
            (_USERS, users),
            (_USERS, passwords),
            (_ADDRESSES, addresses),
            (_BANKS, banks),
            (_SETTINGS, settings),
            (_MILK, milk_configs),
            (_VLCCS, vlccs),
        ):
            if rows:
                await self._session.execute(_by_id_update(table), rows)
