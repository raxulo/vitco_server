"""
Recycle Bin (Phase 7): soft delete of admins, listing, impact preview and the
permanent purge of a record with its ownership tree — against a real SQLite DB.
"""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update

from app.core.clock import now_naive_ist
from app.core.exceptions.base import ForbiddenException
from app.middleware.authentication import CurrentUser
from app.modules.administration.application.command import DeleteUserCommand, ListUsersQuery
from app.modules.administration.application.handler import UserHandler
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.administration.infrastructure.repository import UserRepository
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.collections.vlcc_collection.infrastructure.models import DispatchModel, VlccCollectionModel
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.dashboard.presentation.navigation import build_navigation
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceEnquiryModel,
    MarketplaceOrderItemModel,
    MarketplaceOrderModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
)
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.payments.domain.enums import (
    LedgerEntryType,
    PaymentMethod,
    PaymentSourceType,
    PaymentTransferStatus,
)
from app.modules.payments.infrastructure.models import (
    AccountBalanceModel,
    PaymentLedgerEntryModel,
    PaymentTransferModel,
)
from app.modules.ratechart.domain.enums import MilkType
from app.modules.recyclebin.application.command import (
    GetPurgeImpactQuery,
    ListDeletedRecordsQuery,
    PurgeRecordCommand,
)
from app.modules.recyclebin.application.handler import RecycleBinHandler
from app.modules.recyclebin.domain.enums import DeletedEntityType
from app.modules.recyclebin.domain.exceptions import DeletedRecordNotFoundException
from app.modules.recyclebin.infrastructure.repository import RecycleBinRepository
from app.modules.vlcc.infrastructure.models import VlccModel
from tests.dataexchange.factories import create_farmers, create_user, create_vlcc


class _NoMedia:
    """Media stand-in: these users have no profile images."""

    async def delete_profile_image(self, user_id: UUID, keep_media_id: UUID | None = None) -> int:
        return 0


def _owner(user_id: UUID, role: Role) -> CurrentUser:
    return CurrentUser(id=user_id, role=str(int(role)))


class _InRequest:
    """Runs each handler call inside a transaction, as the web request middleware does."""

    def __init__(self, database, target) -> None:
        self._database = database
        self._target = target

    def __getattr__(self, name):
        method = getattr(self._target, name)

        async def call(*args, **kwargs):
            async with self._database.transaction():
                return await method(*args, **kwargs)

        return call


@pytest.fixture
def bin_handler(database) -> RecycleBinHandler:
    handler = RecycleBinHandler(database=database, repository=RecycleBinRepository(database), media_service=_NoMedia())
    return _InRequest(database, handler)


@pytest.fixture
async def super_admin(database) -> CurrentUser:
    return _owner(await create_user(database, role=Role.SUPER_ADMIN, name="Root"), Role.SUPER_ADMIN)


async def _create_mcc(database, *, created_by: UUID) -> tuple[UUID, UUID]:
    """An MCC centre and its user; returns (mcc_id, user_id)."""
    user_id = await create_user(database, role=Role.MCC, name="MCC user", created_by=created_by)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name="Centre MCC",
                             created_by=created_by))
    return mcc_id, user_id


async def _transfer(database, sender: UUID, receiver: UUID, amount: Decimal) -> UUID:
    """A completed transfer with its two ledger entries and both account balances."""
    transfer_id = uuid4()
    async with database.transaction() as session:
        for user_id, delta in ((sender, -amount), (receiver, amount)):
            row = await session.scalar(select(AccountBalanceModel).where(AccountBalanceModel.user_id == user_id))
            if row is None:
                session.add(AccountBalanceModel(id=uuid4(), user_id=user_id, balance=delta, version=1))
            else:
                row.balance += delta
        session.add(PaymentTransferModel(
            id=transfer_id, sender_id=sender, receiver_id=receiver, amount=amount,
            source_type=PaymentSourceType.MANUAL, payment_method=PaymentMethod.CASH,
            idempotency_key=uuid4().hex, status=PaymentTransferStatus.COMPLETED,
        ))
        await session.flush()
        for user_id, other, entry in ((sender, receiver, LedgerEntryType.DEBIT), (receiver, sender, LedgerEntryType.CREDIT)):
            session.add(PaymentLedgerEntryModel(
                id=uuid4(), transfer_id=transfer_id, user_id=user_id, counterparty_id=other,
                entry_type=entry, amount=amount, balance_before=Decimal(0), balance_after=Decimal(0),
            ))
    return transfer_id


async def _soft_delete_vlcc(database, vlcc) -> None:
    now = now_naive_ist()
    async with database.transaction() as session:
        await session.execute(update(VlccModel).where(VlccModel.id == vlcc.id).values(is_deleted=True, deleted_at=now))
        await session.execute(update(UserModel).where(UserModel.id == vlcc.user_id).values(is_deleted=True, deleted_at=now))


async def _soft_delete_user(database, user_id: UUID) -> None:
    async with database.transaction() as session:
        await session.execute(
            update(UserModel).where(UserModel.id == user_id).values(is_deleted=True, deleted_at=now_naive_ist())
        )


async def _count(database, model, *where) -> int:
    async with database.transaction() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def _balance(database, user_id: UUID) -> Decimal:
    async with database.transaction() as session:
        return await session.scalar(select(AccountBalanceModel.balance).where(AccountBalanceModel.user_id == user_id))


# =========================================================
# ACCESS
# =========================================================

@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC, Role.FARMER])
async def test_recycle_bin_is_super_admin_only(bin_handler, role):
    with pytest.raises(ForbiddenException):
        await bin_handler.list(ListDeletedRecordsQuery(entity_type=DeletedEntityType.VLCC, owner=_owner(uuid4(), role)))


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC, Role.FARMER])
async def test_menu_item_only_for_super_admin(role):
    def hrefs(r):
        return {item.href for group in build_navigation(int(r)) for item in group.items}

    assert "/recycle-bin" in hrefs(Role.SUPER_ADMIN)
    assert "/recycle-bin" not in hrefs(role)


# =========================================================
# ADMIN SOFT DELETE (DECISION-014)
# =========================================================

async def test_sub_admin_delete_is_soft_and_frees_email(database, super_admin, bin_handler):
    sub_id = await create_user(database, role=Role.SUB_ADMIN, name="Soft Sub", created_by=super_admin.id)
    async with database.transaction() as session:
        email_before = await session.scalar(select(UserModel.email).where(UserModel.id == sub_id))

    handler = _InRequest(
        database,
        UserHandler(database=database, repository=UserRepository(database), password=None, media_service=_NoMedia()),
    )
    await handler.delete(DeleteUserCommand(id=sub_id, deleted_by=super_admin.id))

    async with database.transaction() as session:
        row = (await session.execute(select(UserModel).where(UserModel.id == sub_id))).scalar_one()
        assert row.is_deleted and not row.is_active
        assert row.deleted_at is not None and row.deleted_by == super_admin.id
        assert row.email != email_before and row.email.endswith(email_before)

    # Gone from Managed Admins, present in the recycle bin with its original email
    listed = await handler.list(ListUsersQuery(page=1, size=1000, role=Role.SUB_ADMIN, owner=super_admin))
    assert sub_id not in {user.id for user in listed}
    items, _ = await bin_handler.list(
        ListDeletedRecordsQuery(entity_type=DeletedEntityType.SUB_ADMIN, owner=super_admin, search="Soft Sub")
    )
    assert [item.email for item in items if item.id == sub_id] == [email_before]


# =========================================================
# PURGE
# =========================================================

async def test_active_record_cannot_be_purged(database, super_admin, bin_handler):
    vlcc = await create_vlcc(database, created_by=super_admin.id)
    with pytest.raises(DeletedRecordNotFoundException):
        await bin_handler.purge(
            PurgeRecordCommand(entity_type=DeletedEntityType.VLCC, record_id=vlcc.id, owner=super_admin)
        )
    assert await _count(database, VlccModel, VlccModel.id == vlcc.id) == 1


async def test_purge_vlcc_removes_its_data_and_fixes_survivor_balance(database, super_admin, bin_handler):
    survivor_mcc, survivor_user = await _create_mcc(database, created_by=super_admin.id)
    vlcc = await create_vlcc(database, created_by=super_admin.id)
    farmers = await create_farmers(database, vlcc, 2, prefix=f"RB{vlcc.code}")
    farmer_ids = await _farmer_ids(database, vlcc.id)

    async with database.transaction() as session:
        session.add(MccCollectionModel(id=uuid4(), mcc_id=survivor_mcc, vlcc_id=vlcc.id, shift=CollectionShift.MORNING,
                                       milk_type=MilkType.COW))
        session.add(VlccCollectionModel(id=uuid4(), vlcc_id=vlcc.id, farmer_id=farmer_ids[0], milk_type=MilkType.COW,
                                        shift=CollectionShift.MORNING))
        session.add(DispatchModel(id=uuid4(), vlcc_id=vlcc.id))
    await _transfer(database, vlcc.user_id, survivor_user, Decimal("150.00"))
    other_survivor = await create_user(database, role=Role.VLCC, created_by=super_admin.id)
    await _transfer(database, other_survivor, survivor_user, Decimal("40.00"))
    assert await _balance(database, survivor_user) == Decimal("190.00")

    await _soft_delete_vlcc(database, vlcc)

    impact = await bin_handler.impact(
        GetPurgeImpactQuery(entity_type=DeletedEntityType.VLCC, record_id=vlcc.id, owner=super_admin)
    )
    assert (impact.vlccs, impact.farmers, impact.mcc_collections, impact.vlcc_collections) == (1, 2, 1, 1)
    assert (impact.dispatches, impact.payment_transfers, impact.descendants) == (1, 1, 2)
    assert impact.active_records == 2  # the two farmers were never deleted

    await bin_handler.purge(PurgeRecordCommand(entity_type=DeletedEntityType.VLCC, record_id=vlcc.id, owner=super_admin))

    farmer_users = [f["user_id"] for f in farmers]
    assert await _count(database, VlccModel, VlccModel.id == vlcc.id) == 0
    assert await _count(database, FarmerModel, FarmerModel.vlcc_id == vlcc.id) == 0
    assert await _count(database, UserModel, UserModel.id.in_([vlcc.user_id, *farmer_users])) == 0
    assert await _count(database, AddressModel, AddressModel.user_id.in_(farmer_users)) == 0
    assert await _count(database, MccCollectionModel, MccCollectionModel.vlcc_id == vlcc.id) == 0
    assert await _count(database, VlccCollectionModel, VlccCollectionModel.vlcc_id == vlcc.id) == 0
    assert await _count(database, DispatchModel, DispatchModel.vlcc_id == vlcc.id) == 0
    assert await _count(database, PaymentTransferModel, PaymentTransferModel.sender_id == vlcc.user_id) == 0

    # The MCC that received the money stays, minus the removed transfer only
    assert await _count(database, MccModel, MccModel.id == survivor_mcc) == 1
    assert await _balance(database, survivor_user) == Decimal("40.00")
    assert await _count(database, PaymentLedgerEntryModel, PaymentLedgerEntryModel.user_id == survivor_user) == 1


async def test_purge_admin_removes_whole_tree_but_never_super_admin(database, super_admin, bin_handler):
    admin_id = await create_user(database, role=Role.ADMIN, name="Tree Admin", created_by=super_admin.id)
    sub_id = await create_user(database, role=Role.SUB_ADMIN, created_by=admin_id)
    mcc_id, mcc_user = await _create_mcc(database, created_by=admin_id)
    vlcc = await create_vlcc(database, created_by=mcc_user)
    await create_farmers(database, vlcc, 3, prefix=f"T{vlcc.code}")
    outside = await create_vlcc(database, created_by=super_admin.id)
    await _soft_delete_user(database, admin_id)

    impact = await bin_handler.impact(
        GetPurgeImpactQuery(entity_type=DeletedEntityType.ADMIN, record_id=admin_id, owner=super_admin)
    )
    assert (impact.admins, impact.sub_admins, impact.mccs, impact.vlccs, impact.farmers) == (1, 1, 1, 1, 3)
    assert impact.confirm_text == "Tree Admin"

    await bin_handler.purge(PurgeRecordCommand(entity_type=DeletedEntityType.ADMIN, record_id=admin_id, owner=super_admin))

    assert await _count(database, UserModel, UserModel.id.in_([admin_id, sub_id, mcc_user, vlcc.user_id])) == 0
    assert await _count(database, MccModel, MccModel.id == mcc_id) == 0
    assert await _count(database, FarmerModel, FarmerModel.vlcc_id == vlcc.id) == 0
    assert await _count(database, UserModel, UserModel.id == super_admin.id) == 1
    assert await _count(database, VlccModel, VlccModel.id == outside.id) == 1


# =========================================================
# LEGACY MARKETPLACE TABLES (DECISION-015)
# =========================================================


_LEGACY_OWNERS = (
    ("animals", "seller_user_id"),
    ("product_offers", "seller_user_id"),
    ("marketplace_orders", "buyer_id"),
)


@pytest.fixture
async def legacy_tables(database):
    """The old tables as an upgraded database still has them: restricted links to users."""
    async with database.transaction() as session:
        for name, owner in _LEGACY_OWNERS:
            nullability = "NULL" if owner == "buyer_id" else "NOT NULL"
            await session.execute(text(
                f"CREATE TABLE {name} (id CHAR(32) PRIMARY KEY, "
                f"{owner} CHAR(32) {nullability} REFERENCES users(id) ON DELETE RESTRICT)"
            ))
    yield
    async with database.transaction() as session:
        for name, _ in _LEGACY_OWNERS:
            await session.execute(text(f"DROP TABLE {name}"))


async def _add_legacy_rows(database, user_id: UUID) -> None:
    async with database.transaction() as session:
        for name, owner in _LEGACY_OWNERS:
            await session.execute(
                text(f"INSERT INTO {name} (id, {owner}) VALUES (:id, :owner)"),
                {"id": uuid4().hex, "owner": user_id.hex},
            )


async def _legacy_row_counts(database, user_id: UUID) -> list[int]:
    async with database.transaction() as session:
        return [
            await session.scalar(
                text(f"SELECT count(*) FROM {name} WHERE {owner} = :owner"), {"owner": user_id.hex}
            )
            for name, owner in _LEGACY_OWNERS
        ]


async def test_purge_removes_legacy_rows_of_the_tree_only(database, super_admin, bin_handler, legacy_tables):
    admin_id = await create_user(database, role=Role.ADMIN, created_by=super_admin.id)
    survivor = await create_user(database, role=Role.ADMIN, created_by=super_admin.id)
    await _add_legacy_rows(database, admin_id)
    await _add_legacy_rows(database, survivor)
    await _soft_delete_user(database, admin_id)

    impact = await bin_handler.impact(
        GetPurgeImpactQuery(entity_type=DeletedEntityType.ADMIN, record_id=admin_id, owner=super_admin)
    )
    assert impact.marketplace_listings == 2  # one animal and one offer

    await bin_handler.purge(PurgeRecordCommand(entity_type=DeletedEntityType.ADMIN, record_id=admin_id, owner=super_admin))

    assert await _count(database, UserModel, UserModel.id == admin_id) == 0
    assert await _legacy_row_counts(database, admin_id) == [0, 0, 0]
    assert await _legacy_row_counts(database, survivor) == [1, 1, 1]


async def test_purge_works_without_legacy_tables(database, super_admin, bin_handler):
    admin_id = await create_user(database, role=Role.ADMIN, created_by=super_admin.id)
    await _soft_delete_user(database, admin_id)

    impact = await bin_handler.impact(
        GetPurgeImpactQuery(entity_type=DeletedEntityType.ADMIN, record_id=admin_id, owner=super_admin)
    )
    assert impact.marketplace_listings == 0

    await bin_handler.purge(PurgeRecordCommand(entity_type=DeletedEntityType.ADMIN, record_id=admin_id, owner=super_admin))

    assert await _count(database, UserModel, UserModel.id == admin_id) == 0


async def test_purge_removes_new_listings_but_keeps_others_history(database, super_admin, bin_handler):
    admin_id = await create_user(database, role=Role.ADMIN, created_by=super_admin.id)
    other_seller = await create_user(database, role=Role.ADMIN, created_by=super_admin.id)
    suffix = uuid4().hex
    category_id, type_id = uuid4(), uuid4()
    product_id, variant_id, image_id, animal_id, other_product_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    order_id, line_id, enquiry_id = uuid4(), uuid4(), uuid4()

    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=category_id, name="Ghee", slug=f"ghee-{suffix}"))
        session.add(MarketplaceAnimalTypeModel(id=type_id, name=f"Cow {suffix}", slug=f"cow-{suffix}"))
        await session.flush()
        session.add(MarketplaceProductModel(id=product_id, seller_user_id=admin_id, category_id=category_id,
                                            title="Ghee", slug=f"own-{suffix}"))
        session.add(MarketplaceProductModel(id=other_product_id, seller_user_id=other_seller, category_id=category_id,
                                            title="Other", slug=f"other-{suffix}"))
        session.add(MarketplaceAnimalModel(id=animal_id, seller_user_id=admin_id, animal_type_id=type_id, title="Gir",
                                           slug=f"gir-{suffix}", price=Decimal("85000")))
        session.add(MarketplaceOrderModel(id=order_id, order_ref=f"R{suffix[:12]}", buyer_name="Asha",
                                          buyer_phone="9000000000", address_line="Village", pincode="302001",
                                          subtotal=Decimal("500"), total=Decimal("500")))
        await session.flush()
        session.add(MarketplaceProductVariantModel(id=variant_id, product_id=product_id, name="1 L",
                                                   mrp=Decimal("600"), price=Decimal("500"), stock=3))
        session.add(MarketplaceProductImageModel(id=image_id, product_id=product_id, url="/api/v1/media/product/a.jpg"))
        session.add(MarketplaceEnquiryModel(id=enquiry_id, animal_id=animal_id, seller_user_id=admin_id,
                                            animal_title="Gir", buyer_name="Asha", buyer_phone="9000000000"))
        await session.flush()
        session.add(MarketplaceOrderItemModel(id=line_id, order_id=order_id, product_id=product_id, variant_id=variant_id,
                                              seller_user_id=admin_id, product_title="Ghee", variant_name="1 L",
                                              mrp=Decimal("600"), unit_price=Decimal("500"), quantity=1,
                                              line_total=Decimal("500")))
    await _soft_delete_user(database, admin_id)

    impact = await bin_handler.impact(
        GetPurgeImpactQuery(entity_type=DeletedEntityType.ADMIN, record_id=admin_id, owner=super_admin)
    )
    assert impact.marketplace_listings == 2  # one product and one animal

    await bin_handler.purge(PurgeRecordCommand(entity_type=DeletedEntityType.ADMIN, record_id=admin_id, owner=super_admin))

    assert await _count(database, UserModel, UserModel.id == admin_id) == 0
    assert await _count(database, MarketplaceProductModel, MarketplaceProductModel.id == product_id) == 0
    assert await _count(database, MarketplaceProductVariantModel, MarketplaceProductVariantModel.id == variant_id) == 0
    assert await _count(database, MarketplaceProductImageModel, MarketplaceProductImageModel.id == image_id) == 0
    assert await _count(database, MarketplaceAnimalModel, MarketplaceAnimalModel.id == animal_id) == 0
    assert await _count(database, MarketplaceProductModel, MarketplaceProductModel.id == other_product_id) == 1

    async with database.transaction() as session:
        line = await session.get(MarketplaceOrderItemModel, line_id)
        enquiry = await session.get(MarketplaceEnquiryModel, enquiry_id)
        assert (line.product_title, line.product_id, line.variant_id, line.seller_user_id) == ("Ghee", None, None, None)
        assert (enquiry.animal_title, enquiry.animal_id, enquiry.seller_user_id) == ("Gir", None, None)


async def test_purge_twice_is_refused(database, super_admin, bin_handler):
    vlcc = await create_vlcc(database, created_by=super_admin.id)
    await _soft_delete_vlcc(database, vlcc)
    command = PurgeRecordCommand(entity_type=DeletedEntityType.VLCC, record_id=vlcc.id, owner=super_admin)
    await bin_handler.purge(command)
    with pytest.raises(DeletedRecordNotFoundException):
        await bin_handler.purge(command)


async def test_vlcc_delete_records_who_and_when(database, super_admin, bin_handler):
    from app.modules.vlcc.infrastructure.repository import VlccRepository

    vlcc = await create_vlcc(database, created_by=super_admin.id)
    repository = VlccRepository(database)
    async with database.transaction():
        entity = await repository.get_by_id(vlcc.id)
        entity.is_deleted = True
        entity.deleted_at = now_naive_ist()
        entity.deleted_by = super_admin.id
        await repository.update(entity)

    items, _ = await bin_handler.list(
        ListDeletedRecordsQuery(entity_type=DeletedEntityType.VLCC, owner=super_admin, search=vlcc.code)
    )
    row = next(item for item in items if item.id == vlcc.id)
    assert row.deleted_by_name == "Root"
    assert row.deleted_at is not None

    impact = await bin_handler.impact(
        GetPurgeImpactQuery(entity_type=DeletedEntityType.VLCC, record_id=vlcc.id, owner=super_admin)
    )
    assert impact.deleted_by_label == "Root" and impact.deleted_at == row.deleted_at


async def test_deleter_whose_account_is_gone_is_labelled(database, super_admin, bin_handler):
    vlcc = await create_vlcc(database, created_by=super_admin.id)
    await _soft_delete_vlcc(database, vlcc)
    async with database.transaction() as session:
        # deleted_by points at an account that no longer exists
        await session.execute(update(VlccModel).where(VlccModel.id == vlcc.id).values(deleted_by=uuid4()))

    items, _ = await bin_handler.list(
        ListDeletedRecordsQuery(entity_type=DeletedEntityType.VLCC, owner=super_admin, search=vlcc.code)
    )
    row = next(item for item in items if item.id == vlcc.id)
    assert row.deleted_by_name is None
    assert row.deleted_by_label == "Removed account"


async def _farmer_ids(database, vlcc_id: UUID) -> list[UUID]:
    async with database.transaction() as session:
        return list((await session.scalars(select(FarmerModel.id).where(FarmerModel.vlcc_id == vlcc_id))).all())
