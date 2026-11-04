"""
Collection list API: every item carries an accurate `is_deleted`, deleted
collections are returned unless filtered out, and the filter still works.
"""

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.vlcc_collection.infrastructure.models import VlccCollectionModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.ratechart.domain.enums import MilkType
from tests.dataexchange.factories import create_farmers, create_vlcc


async def test_collection_list_reports_is_deleted(api, database, token_for):
    vlcc = await create_vlcc(database)
    await create_farmers(database, vlcc, 1, prefix=f"CL{vlcc.code}")
    active_id, deleted_id = uuid4(), uuid4()
    async with database.transaction() as session:
        farmer_id = await session.scalar(select(FarmerModel.id).where(FarmerModel.vlcc_id == vlcc.id))
        for collection_id, deleted in ((active_id, False), (deleted_id, True)):
            session.add(VlccCollectionModel(
                id=collection_id, vlcc_id=vlcc.id, farmer_id=farmer_id, milk_type=MilkType.COW,
                shift=CollectionShift.MORNING, quantity=Decimal("10.5"), fat_percent=Decimal("4.2"),
                snf_percent=Decimal("8.5"), rate_per_unit=Decimal("40"), total_amount=Decimal("420"),
                is_deleted=deleted,
            ))

    headers = token_for(vlcc.user_id, Role.VLCC)

    response = await api.post("/api/v1/collections/list", json={}, headers=headers)
    assert response.status_code == 200, response.text
    flags = {item["id"]: item["is_deleted"] for item in response.json()["items"]}
    assert flags == {str(active_id): False, str(deleted_id): True}

    only_deleted = await api.post("/api/v1/collections/list", json={"is_deleted": True}, headers=headers)
    assert [item["id"] for item in only_deleted.json()["items"]] == [str(deleted_id)]

    only_active = await api.post("/api/v1/collections/list", json={"is_deleted": False}, headers=headers)
    assert [item["id"] for item in only_active.json()["items"]] == [str(active_id)]
