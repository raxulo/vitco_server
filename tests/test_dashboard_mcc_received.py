"""
Dashboard "MCC Received" leaves out the quantity received at weight-type MCCs;
the plain MCC collection source (used by the MCC's own dashboard) keeps it.
"""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.core.clock import now_naive_ist
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.dashboard.infrastructure.repository import DashboardRepository
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.ratechart.domain.enums import MilkType
from tests.dataexchange.factories import create_user, create_vlcc


async def _mcc(database, created_by: UUID, mcc_type: MccType) -> UUID:
    user_id = await create_user(database, role=Role.MCC, created_by=created_by)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name=f"{mcc_type.name} MCC",
                             mcc_type=mcc_type, created_by=created_by))
    return mcc_id


async def test_mcc_received_excludes_weight_mccs(database):
    admin_id = await create_user(database, role=Role.ADMIN)
    owner = CurrentUser(id=admin_id, role=str(int(Role.ADMIN)))
    normal_mcc = await _mcc(database, admin_id, MccType.NORMAL)
    weight_mcc = await _mcc(database, admin_id, MccType.WEIGHT)
    vlcc = await create_vlcc(database, created_by=admin_id)

    async with database.transaction() as session:
        for mcc_id, quantity in ((normal_mcc, Decimal("120.50")), (weight_mcc, Decimal("80.25"))):
            session.add(MccCollectionModel(
                id=uuid4(), mcc_id=mcc_id, vlcc_id=vlcc.id, shift=CollectionShift.MORNING,
                milk_type=MilkType.COW, quantity=quantity, collected_at=now_naive_ist(),
            ))

    start, end = now_naive_ist() - timedelta(days=1), now_naive_ist() + timedelta(days=1)
    repo = DashboardRepository(database)
    async with database.transaction():
        received = await repo.totals(repo.mcc_collections(owner, exclude_weight=True), start, end)
        everything = await repo.totals(repo.mcc_collections(owner), start, end)

    assert float(received.quantity) == 120.50
    assert float(everything.quantity) == 200.75
