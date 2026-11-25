"""
MCC Weight Date Wise (#37): one row per VLCC with every date in the range added up,
and a Days column counting the distinct days the VLCC had collections.
"""

from datetime import date, datetime
from decimal import Decimal
from secrets import randbelow
from uuid import UUID, uuid4

from sqlalchemy import update

from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.ratechart.domain.enums import MilkType
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.domain.enums import ReportType
from app.modules.reports.executors.mcc.mcc_weight_date_wise import MccWeightDateWiseExecutor
from app.modules.vlcc.infrastructure.models import VlccModel
from tests.dataexchange.factories import create_user, create_vlcc


async def _mcc(database, created_by: UUID) -> UUID:
    user_id = await create_user(database, role=Role.MCC, created_by=created_by)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name="Weight MCC",
                             mcc_type=MccType.WEIGHT, created_by=created_by))
    return mcc_id


def _collection(mcc_id, vlcc_id, at: datetime, shift: CollectionShift, quantity: str, cans: int, *, deleted=False):
    return MccCollectionModel(
        id=uuid4(), mcc_id=mcc_id, vlcc_id=vlcc_id, shift=shift, milk_type=MilkType.COW,
        quantity=Decimal(quantity), can_count=cans, collected_at=at, is_deleted=deleted,
    )


async def test_one_row_per_vlcc_with_days_and_sums(database):
    admin_id = await create_user(database, role=Role.ADMIN)
    mcc_id = await _mcc(database, admin_id)
    first = await create_vlcc(database, created_by=admin_id)
    second = await create_vlcc(database, created_by=admin_id)
    M, E = CollectionShift.MORNING, CollectionShift.EVENING

    async with database.transaction() as session:
        # Real VLCC codes are numbers; the report sorts them as integers
        codes = {first.id: str(900000 + randbelow(9000)), second.id: str(910000 + randbelow(9000))}
        for vlcc_id, code in codes.items():
            await session.execute(update(VlccModel).where(VlccModel.id == vlcc_id).values(vlcc_code=code))
        session.add_all([
            # first VLCC: three dates, two shifts on the first one
            _collection(mcc_id, first.id, datetime(2026, 11, 1, 7), M, "100.50", 3),
            _collection(mcc_id, first.id, datetime(2026, 11, 1, 18), E, "50.25", 2),
            _collection(mcc_id, first.id, datetime(2026, 11, 2, 7), M, "80.00", 2),
            _collection(mcc_id, first.id, datetime(2026, 11, 5, 7), M, "40.00", 1),
            # deleted entries never count
            _collection(mcc_id, first.id, datetime(2026, 11, 6, 7), M, "999.00", 9, deleted=True),
            # second VLCC: one date
            _collection(mcc_id, second.id, datetime(2026, 11, 3, 7), M, "60.00", 2),
            # outside the range
            _collection(mcc_id, second.id, datetime(2026, 11, 20, 7), M, "70.00", 2),
        ])

    query = ReportQuery(
        actor_id=admin_id, report_type=ReportType.MCC_WEIGHT_DATE_WISE, mcc_id=mcc_id,
        start_date=date(2026, 11, 1), end_date=date(2026, 11, 10),
    )
    async with database.transaction():
        result = await MccWeightDateWiseExecutor(database).execute(query)

    assert result.header == ["V.Code", "Days", "Name", "Can", "Quantity"]
    rows = result.ledger[0].rows
    assert [row["vlcc_code"] for row in rows] == [codes[first.id], codes[second.id]]
    assert list(rows[0]) == ["vlcc_code", "days", "vlcc_name", "can", "quantity"]

    assert rows[0]["days"] == 3
    assert rows[0]["can"] == 8
    assert float(rows[0]["quantity"]) == 270.75
    assert rows[1]["days"] == 1
    assert rows[1]["can"] == 2
    assert float(rows[1]["quantity"]) == 60.00

    # Totals live in the ledger footer (#38); the report-level footer is empty
    footer = result.ledger[0].footer
    assert footer["total_vlcc"] == 2
    assert footer["total_cans"] == 10
    assert float(footer["total_quantity"]) == 330.75
    assert result.footer == {}
