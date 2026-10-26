"""
Tests for Login Access Scoped Rate Charts (Repository & Excel Exchange Scope):
- SuperAdmin: All access (view and modify all charts)
- Admin: Views own, SubAdmins' (below), MCCs'/VLCCs' (below), SuperAdmin's charts.
         Can modify own and users below it. CANNOT modify SuperAdmin's charts.
         Cannot view other Admin trees.
- SubAdmin: Views own, MCCs'/VLCCs' (below), parent Admin's charts, SuperAdmin's charts.
            Can modify own and MCCs/VLCCs below it. CANNOT modify parent Admin or SuperAdmin charts.
            Cannot view other Admin or SubAdmin trees.
- MCC / VLCC: Views ONLY own charts and assigned charts.
              Can modify ONLY own charts. Assigned charts are strictly read-only.
"""

from uuid import uuid4
import pytest

from app.core.clock import now_naive_ist
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.ratechart.domain.enums import RateChartType
from app.modules.ratechart.infrastructure.models import RateChartAssignmentModel, RateChartModel
from app.modules.ratechart.infrastructure.repository import RateChartAccessScope, RateChartRepository
from app.modules.dataexchange.infrastructure.ratechart_scope import RateChartScope
from app.modules.vlcc.infrastructure.models import VlccModel
from tests.dataexchange.factories import (
    create_formula_chart,
    create_prodata_chart,
    create_user,
    unique_mobile,
)


@pytest.mark.asyncio
async def test_superadmin_full_access(database):
    super_admin = await create_user(database, role=Role.SUPER_ADMIN, name="Super User")
    admin = await create_user(database, role=Role.ADMIN, name="Admin", created_by=super_admin)
    mcc_user = await create_user(database, role=Role.MCC, name="MCC User", created_by=admin)

    chart_super = await create_prodata_chart(database, name="Super Chart", created_by=super_admin)
    chart_admin = await create_prodata_chart(database, name="Admin Chart", created_by=admin)
    chart_mcc = await create_prodata_chart(database, name="MCC Chart", created_by=mcc_user)

    user_ctx = CurrentUser(id=super_admin, role=str(Role.SUPER_ADMIN.value))
    repo = RateChartRepository(database)
    scope = RateChartScope(database)

    # Repository list
    async with database.transaction():
        charts = await repo.list(offset=0, limit=100, owner=user_ctx)
        chart_map = {c.id: c for c in charts}
        assert chart_super in chart_map
        assert chart_admin in chart_map
        assert chart_mcc in chart_map
        assert chart_map[chart_super].can_modify is True
        assert chart_map[chart_admin].can_modify is True
        assert chart_map[chart_mcc].can_modify is True

    # DataExchange Scope options
    async with database.transaction():
        opts = await scope.options(user_ctx)
        opt_map = {i.id: i for i in opts.items}
        assert chart_super in opt_map and opt_map[chart_super].can_modify is True
        assert chart_admin in opt_map and opt_map[chart_admin].can_modify is True
        assert chart_mcc in opt_map and opt_map[chart_mcc].can_modify is True


@pytest.mark.asyncio
async def test_admin_access_rules(database):
    now = now_naive_ist()
    super_admin = await create_user(database, role=Role.SUPER_ADMIN, name="Super")
    admin_a = await create_user(database, role=Role.ADMIN, name="Admin A")
    admin_b = await create_user(database, role=Role.ADMIN, name="Admin B")

    sub_admin_a = await create_user(database, role=Role.SUB_ADMIN, name="Sub Admin A", created_by=admin_a)
    mcc_a_user = await create_user(database, role=Role.MCC, name="MCC A User", created_by=admin_a)
    vlcc_a_user = await create_user(database, role=Role.VLCC, name="VLCC A User", created_by=admin_a)

    # Link MCC & VLCC records
    async with database.transaction() as session:
        await session.execute(MccModel.__table__.insert(), [dict(
            id=uuid4(), user_id=mcc_a_user, mcc_code="MCC001", name="MCC Center",
            created_by=admin_a, created_at=now, updated_at=now, is_deleted=False, is_active=True,
        )])
        await session.execute(VlccModel.__table__.insert(), [dict(
            id=uuid4(), user_id=vlcc_a_user, uic_code="UV001", vlcc_code="V001", name="VLCC Center",
            farmer_enabled=True, is_active=True, created_by=admin_a, created_at=now, updated_at=now,
            is_deleted=False, soc_percentage=0.0, assigned_chart_rank=1,
        )])

    chart_super = await create_prodata_chart(database, name="Super Chart", created_by=super_admin)
    chart_admin_a = await create_prodata_chart(database, name="Admin A Chart", created_by=admin_a)
    chart_sub_a = await create_prodata_chart(database, name="SubAdmin A Chart", created_by=sub_admin_a)
    chart_mcc_a = await create_prodata_chart(database, name="MCC A Chart", created_by=mcc_a_user)
    chart_vlcc_a = await create_prodata_chart(database, name="VLCC A Chart", created_by=vlcc_a_user)
    chart_admin_b = await create_prodata_chart(database, name="Admin B Chart", created_by=admin_b)

    user_ctx = CurrentUser(id=admin_a, role=str(Role.ADMIN.value))
    repo = RateChartRepository(database)
    scope = RateChartScope(database)

    async with database.transaction():
        charts = await repo.list(offset=0, limit=100, owner=user_ctx)
        chart_map = {c.id: c for c in charts}

        # Admin A sees SuperAdmin, own, SubAdmin A, MCC A, VLCC A
        assert chart_super in chart_map
        assert chart_admin_a in chart_map
        assert chart_sub_a in chart_map
        assert chart_mcc_a in chart_map
        assert chart_vlcc_a in chart_map

        # Admin A CANNOT see Admin B's chart
        assert chart_admin_b not in chart_map

        # Admin A CANNOT modify SuperAdmin's chart
        assert chart_map[chart_super].can_modify is False

        # Admin A CAN modify its own, SubAdmin A, MCC A, VLCC A charts
        assert chart_map[chart_admin_a].can_modify is True
        assert chart_map[chart_sub_a].can_modify is True
        assert chart_map[chart_mcc_a].can_modify is True
        assert chart_map[chart_vlcc_a].can_modify is True

    # DataExchange Scope check
    async with database.transaction():
        opts = await scope.options(user_ctx)
        opt_map = {i.id: i for i in opts.items}
        assert chart_super in opt_map and opt_map[chart_super].can_modify is False
        assert chart_admin_a in opt_map and opt_map[chart_admin_a].can_modify is True
        assert chart_sub_a in opt_map and opt_map[chart_sub_a].can_modify is True
        assert chart_admin_b not in opt_map


@pytest.mark.asyncio
async def test_subadmin_access_rules(database):
    now = now_naive_ist()
    super_admin = await create_user(database, role=Role.SUPER_ADMIN, name="Super")
    admin = await create_user(database, role=Role.ADMIN, name="Parent Admin")
    sub_admin = await create_user(database, role=Role.SUB_ADMIN, name="Sub Admin", created_by=admin)
    mcc_user = await create_user(database, role=Role.MCC, name="MCC under Sub", created_by=sub_admin)
    other_admin = await create_user(database, role=Role.ADMIN, name="Other Admin")

    async with database.transaction() as session:
        await session.execute(MccModel.__table__.insert(), [dict(
            id=uuid4(), user_id=mcc_user, mcc_code="MCC002", name="MCC Center 2",
            created_by=sub_admin, created_at=now, updated_at=now, is_deleted=False, is_active=True,
        )])

    chart_super = await create_prodata_chart(database, name="Super Chart", created_by=super_admin)
    chart_parent_admin = await create_prodata_chart(database, name="Parent Admin Chart", created_by=admin)
    chart_sub = await create_prodata_chart(database, name="Sub Admin Chart", created_by=sub_admin)
    chart_mcc = await create_prodata_chart(database, name="MCC under Sub Chart", created_by=mcc_user)
    chart_other = await create_prodata_chart(database, name="Other Admin Chart", created_by=other_admin)

    user_ctx = CurrentUser(id=sub_admin, role=str(Role.SUB_ADMIN.value))
    repo = RateChartRepository(database)
    scope = RateChartScope(database)

    async with database.transaction():
        charts = await repo.list(offset=0, limit=100, owner=user_ctx)
        chart_map = {c.id: c for c in charts}

        # SubAdmin sees SuperAdmin, Parent Admin, own, and MCC created under it
        assert chart_super in chart_map
        assert chart_parent_admin in chart_map
        assert chart_sub in chart_map
        assert chart_mcc in chart_map

        # SubAdmin does NOT see other Admin's chart
        assert chart_other not in chart_map

        # SuperAdmin and Parent Admin charts are strictly READ-ONLY for SubAdmin
        assert chart_map[chart_super].can_modify is False
        assert chart_map[chart_parent_admin].can_modify is False

        # SubAdmin CAN modify its own and MCC created under it
        assert chart_map[chart_sub].can_modify is True
        assert chart_map[chart_mcc].can_modify is True

    async with database.transaction():
        opts = await scope.options(user_ctx)
        opt_map = {i.id: i for i in opts.items}
        assert chart_super in opt_map and opt_map[chart_super].can_modify is False
        assert chart_parent_admin in opt_map and opt_map[chart_parent_admin].can_modify is False
        assert chart_sub in opt_map and opt_map[chart_sub].can_modify is True
        assert chart_other not in opt_map


@pytest.mark.asyncio
async def test_mcc_and_vlcc_access_rules(database):
    now = now_naive_ist()
    super_admin = await create_user(database, role=Role.SUPER_ADMIN, name="Super")
    admin = await create_user(database, role=Role.ADMIN, name="Admin")
    vlcc_user = await create_user(database, role=Role.VLCC, name="VLCC User", created_by=admin)

    # 1 unassigned super chart, 1 unassigned admin chart
    chart_super_unassigned = await create_prodata_chart(database, name="Super Unassigned", created_by=super_admin)
    chart_admin_unassigned = await create_prodata_chart(database, name="Admin Unassigned", created_by=admin)

    # 1 chart created by VLCC itself
    chart_vlcc_own = await create_prodata_chart(database, name="VLCC Own Chart", created_by=vlcc_user)

    # 1 chart created by Admin and ASSIGNED to VLCC
    chart_assigned = await create_prodata_chart(database, name="Assigned Chart", created_by=admin)
    async with database.transaction() as session:
        await session.execute(RateChartAssignmentModel.__table__.insert(), [dict(
            id=uuid4(), owner_type=Role.VLCC, owner_id=vlcc_user,
            rate_chart_id=chart_assigned, is_active=True, created_at=now, updated_at=now,
        )])

    user_ctx = CurrentUser(id=vlcc_user, role=str(Role.VLCC.value))
    repo = RateChartRepository(database)
    scope = RateChartScope(database)

    async with database.transaction():
        charts = await repo.list(offset=0, limit=100, owner=user_ctx)
        chart_map = {c.id: c for c in charts}

        # VLCC ONLY sees its own chart AND assigned chart
        assert chart_vlcc_own in chart_map
        assert chart_assigned in chart_map

        # VLCC CANNOT see unassigned SuperAdmin or Admin charts
        assert chart_super_unassigned not in chart_map
        assert chart_admin_unassigned not in chart_map

        # VLCC can modify ONLY its own chart
        assert chart_map[chart_vlcc_own].can_modify is True

        # Assigned chart is strictly READ-ONLY for VLCC
        assert chart_map[chart_assigned].can_modify is False

    # Check DataExchange scope options
    async with database.transaction():
        opts = await scope.options(user_ctx)
        opt_map = {i.id: i for i in opts.items}
        assert chart_vlcc_own in opt_map and opt_map[chart_vlcc_own].can_modify is True
        assert chart_assigned in opt_map and opt_map[chart_assigned].can_modify is False
        assert chart_super_unassigned not in opt_map
        assert chart_admin_unassigned not in opt_map
