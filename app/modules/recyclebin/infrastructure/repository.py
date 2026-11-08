"""
Recycle Bin repository.

Lists soft-deleted Admins / Sub Admins / MCCs / VLCCs / Farmers and permanently
deletes one of them together with its ownership tree and every row that points
at it (DECISION-013). Foreign keys are enforced, so rows are removed children
first, with bulk statements over id chunks.

Python 3.13+
"""

import re
from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.advanceditem.infrastructure.models import AdvanceRecordModel
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.collections.vlcc_collection.infrastructure.models import (
    DispatchModel,
    VlccCollectionModel,
)
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.common.fixedrate_config.infrastructure.models import FixedRateConfigModel
from app.modules.common.milk_quality.infrastructure.models import MilkQualityConfigModel
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.marketplace.infrastructure.models import (
    AnimalModel,
    MarketplaceOrderModel,
    ProductOfferModel,
)
from app.modules.masters.advanced.infrastructure.models import AdvanceMasterModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.payments.domain.enums import LedgerEntryType
from app.modules.payments.infrastructure.models import (
    AccountBalanceModel,
    PaymentLedgerEntryModel,
    PaymentTransferModel,
)
from app.modules.ratechart.infrastructure.models import RateChartAssignmentModel, RateChartModel
from app.modules.recyclebin.domain.dto import DeletedRecordDto, PurgeScope
from app.modules.recyclebin.domain.enums import DeletedEntityType
from app.modules.recyclebin.domain.irepository import IRecycleBinRepository
from app.modules.vlcc.infrastructure.models import VlccModel

# Keeps every IN (...) well below SQLite's bound-parameter limit
_CHUNK = 500

# Soft delete frees unique values with these markers; strip them for display
_DELETED_PREFIX = re.compile(r"^del_[0-9a-f]{6}_")
_DELETED_SUFFIX = re.compile(r"__del_[0-9a-f]{6}$")

_USER_ROLE = {
    DeletedEntityType.ADMIN: Role.ADMIN,
    DeletedEntityType.SUB_ADMIN: Role.SUB_ADMIN,
}


def _chunks(values: Iterable[UUID]) -> Iterable[list[UUID]]:
    items = list(values)
    for start in range(0, len(items), _CHUNK):
        yield items[start:start + _CHUNK]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return _DELETED_SUFFIX.sub("", _DELETED_PREFIX.sub("", value))


class RecycleBinRepository(IRecycleBinRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # LIST
    # =========================================================

    async def list_deleted(
        self,
        entity_type: DeletedEntityType,
        search: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[DeletedRecordDto], int]:
        stmt = self._listing(entity_type)
        if search and search.strip():
            stmt = stmt.where(self._search_condition(entity_type, f"%{search.strip()}%"))

        total = await self._session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ) or 0
        rows = (await self._session.execute(stmt.offset(offset).limit(limit))).all()
        return [self._to_dto(entity_type, row) for row in rows], total

    async def get_deleted(
        self,
        entity_type: DeletedEntityType,
        record_id: UUID,
    ) -> tuple[DeletedRecordDto, UUID] | None:
        stmt = self._listing(entity_type).where(self._id_column(entity_type) == record_id)
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        return self._to_dto(entity_type, row), row.user_id

    def _listing(self, entity_type: DeletedEntityType):
        """SELECT of one tab: id, user_id, code, name, email, mobile, parent, deleted_at, deleted_by."""
        deleter = aliased(UserModel, name="deleter")
        creator = aliased(UserModel, name="creator")

        if entity_type in _USER_ROLE:
            return (
                select(
                    UserModel.id.label("id"),
                    UserModel.id.label("user_id"),
                    UserModel.name.label("code"),
                    UserModel.name.label("name"),
                    UserModel.email.label("email"),
                    UserModel.mobile.label("mobile"),
                    creator.name.label("parent_name"),
                    UserModel.deleted_at.label("deleted_at"),
                    deleter.name.label("deleted_by_name"),
                    UserModel.deleted_by.label("deleted_by_id"),
                )
                .outerjoin(creator, creator.id == UserModel.created_by)
                .outerjoin(deleter, deleter.id == UserModel.deleted_by)
                .where(
                    UserModel.is_deleted.is_(True),
                    UserModel.role == _USER_ROLE[entity_type],
                )
                # Portable "NULLS LAST" (SQLite < 3.30 has no NULLS LAST syntax)
                .order_by(
                    UserModel.deleted_at.is_(None), UserModel.deleted_at.desc(), UserModel.name
                )
            )

        if entity_type == DeletedEntityType.MCC:
            master, code = MccModel, MccModel.code
            parent = creator.name
            parent_join = (creator, creator.id == MccModel.created_by)
        elif entity_type == DeletedEntityType.VLCC:
            master, code = VlccModel, VlccModel.vlcc_code
            parent = creator.name
            parent_join = (creator, creator.id == VlccModel.created_by)
        else:
            master, code = FarmerModel, FarmerModel.farmer_code
            parent = VlccModel.name
            parent_join = (VlccModel, VlccModel.id == FarmerModel.vlcc_id)

        name = UserModel.name if master is FarmerModel else master.name
        # Portable "NULLS LAST" (SQLite < 3.30 has no NULLS LAST syntax)
        deleted_at = func.coalesce(master.deleted_at, UserModel.deleted_at)
        return (
            select(
                master.id.label("id"),
                master.user_id.label("user_id"),
                code.label("code"),
                name.label("name"),
                UserModel.email.label("email"),
                UserModel.mobile.label("mobile"),
                parent.label("parent_name"),
                func.coalesce(master.deleted_at, UserModel.deleted_at).label("deleted_at"),
                deleter.name.label("deleted_by_name"),
                func.coalesce(master.deleted_by, UserModel.deleted_by).label("deleted_by_id"),
            )
            .join(UserModel, UserModel.id == master.user_id)
            .outerjoin(*parent_join)
            .outerjoin(deleter, deleter.id == func.coalesce(master.deleted_by, UserModel.deleted_by))
            .where(master.is_deleted.is_(True))
            .order_by(deleted_at.is_(None), deleted_at.desc(), name)
        )

    @staticmethod
    def _id_column(entity_type: DeletedEntityType):
        return {
            DeletedEntityType.MCC: MccModel.id,
            DeletedEntityType.VLCC: VlccModel.id,
            DeletedEntityType.FARMER: FarmerModel.id,
        }.get(entity_type, UserModel.id)

    @staticmethod
    def _search_condition(entity_type: DeletedEntityType, pattern: str):
        columns = [UserModel.name, UserModel.email, UserModel.mobile]
        if entity_type == DeletedEntityType.MCC:
            columns += [MccModel.name, MccModel.code]
        elif entity_type == DeletedEntityType.VLCC:
            columns += [VlccModel.name, VlccModel.vlcc_code]
        elif entity_type == DeletedEntityType.FARMER:
            columns.append(FarmerModel.farmer_code)
        return or_(*(column.ilike(pattern) for column in columns))

    @staticmethod
    def _to_dto(entity_type: DeletedEntityType, row) -> DeletedRecordDto:
        return DeletedRecordDto(
            id=row.id,
            entity_type=entity_type,
            code=None if entity_type in _USER_ROLE else _clean(row.code),
            name=row.name,
            email=_clean(row.email),
            mobile=_clean(row.mobile),
            parent_name=row.parent_name,
            deleted_at=row.deleted_at,
            deleted_by_name=row.deleted_by_name,
            deleted_by_id=row.deleted_by_id,
        )

    # =========================================================
    # SCOPE (ownership tree)
    # =========================================================

    async def resolve_scope(self, root_user_id: UUID) -> PurgeScope:
        users = {root_user_id}
        frontier = {root_user_id}

        while frontier:
            found: set[UUID] = set()
            for chunk in _chunks(frontier):
                found |= await self._ids(select(UserModel.id).where(UserModel.created_by.in_(chunk)))
                found |= await self._ids(select(MccModel.user_id).where(MccModel.created_by.in_(chunk)))
                found |= await self._ids(select(VlccModel.user_id).where(VlccModel.created_by.in_(chunk)))
                found |= await self._ids(
                    select(FarmerModel.user_id).where(
                        or_(
                            FarmerModel.created_by.in_(chunk),
                            FarmerModel.vlcc_id.in_(select(VlccModel.id).where(VlccModel.user_id.in_(chunk))),
                        )
                    )
                )
            frontier = found - users
            users |= frontier

        # Super Admins are never removed, whatever created them
        users -= await self._in(select(UserModel.id).where(UserModel.role == Role.SUPER_ADMIN), UserModel.id, users)

        scope = PurgeScope(root_user_id=root_user_id, user_ids=users)
        scope.mcc_ids = await self._in(select(MccModel.id), MccModel.user_id, users)
        scope.vlcc_ids = await self._in(select(VlccModel.id), VlccModel.user_id, users)
        scope.farmer_ids = (
            await self._in(select(FarmerModel.id), FarmerModel.user_id, users)
            | await self._in(select(FarmerModel.id), FarmerModel.vlcc_id, scope.vlcc_ids)
        )
        return scope

    # =========================================================
    # IMPACT
    # =========================================================

    async def count_impact(self, scope: PurgeScope) -> dict[str, int]:
        users = scope.user_ids
        roles: dict[Role, int] = defaultdict(int)
        active = 0
        for chunk in _chunks(users):
            rows = await self._session.execute(
                select(UserModel.role, UserModel.is_deleted).where(UserModel.id.in_(chunk))
            )
            for role, is_deleted in rows:
                roles[Role(role)] += 1
                active += 0 if is_deleted else 1

        return {
            "admins": roles[Role.ADMIN],
            "sub_admins": roles[Role.SUB_ADMIN],
            "mccs": len(scope.mcc_ids),
            "vlccs": len(scope.vlcc_ids),
            "farmers": len(scope.farmer_ids),
            "active_records": active,
            "mcc_collections": len(await self._mcc_collection_ids(scope)),
            "vlcc_collections": len(await self._vlcc_collection_ids(scope)),
            "dispatches": len(await self._in(select(DispatchModel.id), DispatchModel.vlcc_id, scope.vlcc_ids)),
            "payment_transfers": len(await self._transfer_ids(users)),
            "rate_charts": len(await self._rate_chart_ids(users)),
            "advances": len(await self._advance_record_ids(users))
            + len(await self._in(select(AdvanceMasterModel.id), AdvanceMasterModel.user_id, users)),
            "marketplace_listings": len(await self._in(select(AnimalModel.id), AnimalModel.seller_user_id, users))
            + len(await self._in(select(ProductOfferModel.id), ProductOfferModel.seller_user_id, users)),
        }

    # =========================================================
    # PURGE
    # =========================================================

    async def purge(self, scope: PurgeScope) -> None:
        users = scope.user_ids

        # 1. Payments: keep surviving counterparties' balances right, then drop the transfers
        transfer_ids = await self._transfer_ids(users)
        await self._reverse_survivor_balances(transfer_ids, users)
        await self._delete_in(PaymentLedgerEntryModel, PaymentLedgerEntryModel.transfer_id, transfer_ids)
        await self._delete_in(PaymentTransferModel, PaymentTransferModel.id, transfer_ids)

        # 2. Collections and dispatches of the tree's centres and farmers
        await self._delete_in(VlccCollectionModel, VlccCollectionModel.id, await self._vlcc_collection_ids(scope))
        await self._delete_in(MccCollectionModel, MccCollectionModel.id, await self._mcc_collection_ids(scope))
        await self._delete_in(DispatchModel, DispatchModel.vlcc_id, scope.vlcc_ids)

        # 3. Advances and marketplace rows owned by the tree's users
        await self._delete_in(AdvanceRecordModel, AdvanceRecordModel.id, await self._advance_record_ids(users))
        await self._delete_in(AdvanceMasterModel, AdvanceMasterModel.user_id, users)
        await self._delete_in(AnimalModel, AnimalModel.seller_user_id, users)
        await self._delete_in(ProductOfferModel, ProductOfferModel.seller_user_id, users)
        await self._delete_in(MarketplaceOrderModel, MarketplaceOrderModel.buyer_id, users)

        # 4. Rate charts made inside the tree that no survivor uses; survivors' charts stay
        await self._delete_in(RateChartModel, RateChartModel.id, await self._rate_chart_ids(users))
        await self._null_in(RateChartAssignmentModel, RateChartAssignmentModel.created_by, users)

        # 5. Masters (farmers first: they point at VLCCs)
        links = await self._master_links(scope)
        await self._delete_in(FarmerModel, FarmerModel.id, scope.farmer_ids)
        await self._delete_in(VlccModel, VlccModel.id, scope.vlcc_ids)
        await self._delete_in(MccModel, MccModel.id, scope.mcc_ids)

        # 6. Per-user records the masters pointed at; survivors never keep a dangling link
        for model, column in (
            (AddressModel, "address_id"),
            (BankAccountModel, "bank_account_id"),
            (FixedRateConfigModel, "fixed_rate_config_id"),
            (MilkQualityConfigModel, "milk_quality_config_id"),
        ):
            owned = await self._in(select(model.id), model.user_id, users)
            await self._detach_survivors(column, owned)
            await self._delete_in(model, model.id, owned)
        await self._delete_unused_settings(links["settings_id"])

        # 7. Users: clear in-tree and survivor creator links, then delete
        for model in (UserModel, MccModel, VlccModel, FarmerModel):
            await self._null_in(model, model.created_by, users)
        await self._delete_in(UserModel, UserModel.id, users)

    # =========================================================
    # PURGE HELPERS
    # =========================================================

    async def _reverse_survivor_balances(self, transfer_ids: set[UUID], users: set[UUID]) -> None:
        """Undo each survivor ledger entry of a deleted transfer on its account balance."""
        deltas: dict[UUID, Decimal] = defaultdict(Decimal)
        for chunk in _chunks(transfer_ids):
            rows = await self._session.execute(
                select(
                    PaymentLedgerEntryModel.user_id,
                    PaymentLedgerEntryModel.entry_type,
                    PaymentLedgerEntryModel.amount,
                ).where(PaymentLedgerEntryModel.transfer_id.in_(chunk))
            )
            for user_id, entry_type, amount in rows:
                if user_id in users:
                    continue
                amount = Decimal(amount or 0)
                deltas[user_id] += -amount if entry_type == LedgerEntryType.CREDIT else amount

        for user_id, delta in deltas.items():
            if delta:
                await self._session.execute(
                    update(AccountBalanceModel)
                    .where(AccountBalanceModel.user_id == user_id)
                    .values(
                        balance=AccountBalanceModel.balance + delta,
                        version=AccountBalanceModel.version + 1,
                    )
                    .execution_options(synchronize_session=False)
                )

    async def _master_links(self, scope: PurgeScope) -> dict[str, set[UUID]]:
        settings: set[UUID] = set()
        for model, ids in ((MccModel, scope.mcc_ids), (VlccModel, scope.vlcc_ids)):
            settings |= await self._in(select(model.settings_id), model.id, ids)
        settings.discard(None)
        return {"settings_id": settings}

    async def _detach_survivors(self, column: str, ids: set[UUID]) -> None:
        """Survivor masters pointing at a row being deleted lose the link instead of blocking it."""
        for model in (MccModel, VlccModel, FarmerModel):
            if hasattr(model, column):
                await self._null_in(model, getattr(model, column), ids)

    async def _delete_unused_settings(self, settings_ids: set[UUID]) -> None:
        still_used = (
            await self._in(select(MccModel.settings_id), MccModel.settings_id, settings_ids)
            | await self._in(select(VlccModel.settings_id), VlccModel.settings_id, settings_ids)
        )
        await self._delete_in(SettingsModel, SettingsModel.id, settings_ids - still_used)

    async def _transfer_ids(self, users: set[UUID]) -> set[UUID]:
        return (
            await self._in(select(PaymentTransferModel.id), PaymentTransferModel.sender_id, users)
            | await self._in(select(PaymentTransferModel.id), PaymentTransferModel.receiver_id, users)
        )

    async def _vlcc_collection_ids(self, scope: PurgeScope) -> set[UUID]:
        return (
            await self._in(select(VlccCollectionModel.id), VlccCollectionModel.vlcc_id, scope.vlcc_ids)
            | await self._in(select(VlccCollectionModel.id), VlccCollectionModel.farmer_id, scope.farmer_ids)
        )

    async def _mcc_collection_ids(self, scope: PurgeScope) -> set[UUID]:
        return (
            await self._in(select(MccCollectionModel.id), MccCollectionModel.mcc_id, scope.mcc_ids)
            | await self._in(select(MccCollectionModel.id), MccCollectionModel.vlcc_id, scope.vlcc_ids)
        )

    async def _advance_record_ids(self, users: set[UUID]) -> set[UUID]:
        return (
            await self._in(select(AdvanceRecordModel.id), AdvanceRecordModel.user_id, users)
            | await self._in(select(AdvanceRecordModel.id), AdvanceRecordModel.created_by, users)
        )

    async def _rate_chart_ids(self, users: set[UUID]) -> set[UUID]:
        """Charts created in the tree, minus those still assigned to a surviving user."""
        created = await self._in(select(RateChartModel.id), RateChartModel.created_by, users)
        used_by_survivor: set[UUID] = set()
        for chunk in _chunks(created):
            rows = await self._session.execute(
                select(RateChartAssignmentModel.rate_chart_id, RateChartAssignmentModel.owner_id)
                .where(RateChartAssignmentModel.rate_chart_id.in_(chunk))
            )
            used_by_survivor |= {chart_id for chart_id, owner_id in rows if owner_id not in users}
        return created - used_by_survivor

    async def _ids(self, stmt) -> set[UUID]:
        return {value for value in (await self._session.scalars(stmt)).all() if value is not None}

    async def _in(self, stmt, column, values: set[UUID]) -> set[UUID]:
        found: set[UUID] = set()
        for chunk in _chunks(values):
            found |= await self._ids(stmt.where(column.in_(chunk)))
        return found

    async def _delete_in(self, model, column, values: set[UUID]) -> None:
        for chunk in _chunks(values):
            await self._session.execute(
                delete(model).where(column.in_(chunk)).execution_options(synchronize_session=False)
            )

    async def _null_in(self, model, column, values: set[UUID]) -> None:
        for chunk in _chunks(values):
            await self._session.execute(
                update(model)
                .where(column.in_(chunk))
                .values({column.key: None})
                .execution_options(synchronize_session=False)
            )
