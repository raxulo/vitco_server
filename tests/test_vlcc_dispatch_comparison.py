import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from sqlalchemy import insert
from starlette.datastructures import QueryParams

from app.core.clock import now_naive_ist
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    QuantityCollectionMode,
    MeasurementMode,
)
from app.modules.ratechart.domain.enums import MilkType
from app.modules.collections.vlcc_collection.infrastructure.models import (
    VlccCollectionModel,
    DispatchModel,
)
from app.middleware.authentication import CurrentUser
from app.modules.collections.vlcc_collection.application.dispatch_handler import DispatchHandler
from app.modules.collections.vlcc_collection.infrastructure.dispatch_repository import DispatchRepository
from app.web.vlcc_dispatch.controller import DispatchController


@pytest.mark.asyncio
async def test_vlcc_dispatch_collection_comparison(database):
    admin_id = uuid4()
    vlcc_user_id = uuid4()
    vlcc_id = uuid4()
    farmer_user_id = uuid4()
    farmer_id = uuid4()

    today_dt = now_naive_ist()

    async with database.transaction() as session:
        # 1. Admin
        await session.execute(
            insert(UserModel).values([
                {
                    "id": admin_id,
                    "name": "Super Admin",
                    "email": f"admin-{admin_id.hex[:6]}@test.local",
                    "mobile": f"9{str(admin_id.int)[-9:]}",
                    "password_hash": "hash",
                    "role": Role.ADMIN,
                    "created_by": None,
                    "created_at": today_dt,
                    "updated_at": today_dt,
                },
                # 2. VLCC user
                {
                    "id": vlcc_user_id,
                    "name": "VLCC Center Incharge",
                    "email": f"vlcc-{vlcc_user_id.hex[:6]}@test.local",
                    "mobile": f"9{str(vlcc_user_id.int)[-9:]}",
                    "password_hash": "hash",
                    "role": Role.VLCC,
                    "created_by": admin_id,
                    "created_at": today_dt,
                    "updated_at": today_dt,
                },
                # 3. Farmer user
                {
                    "id": farmer_user_id,
                    "name": "Ramesh Kumar",
                    "email": f"farmer-{farmer_user_id.hex[:6]}@test.local",
                    "mobile": f"9{str(farmer_user_id.int)[-9:]}",
                    "password_hash": "hash",
                    "role": Role.FARMER,
                    "created_by": vlcc_user_id,
                    "created_at": today_dt,
                    "updated_at": today_dt,
                },
            ])
        )

        # 4. VLCC Model (created by Admin)
        await session.execute(
            insert(VlccModel).values({
                "id": vlcc_id,
                "name": "Green Dairy VLCC",
                "uic_code": "UIC-001",
                "vlcc_code": "VLCC-001",
                "user_id": vlcc_user_id,
                "created_by": admin_id,
                "created_at": today_dt,
                "updated_at": today_dt,
            })
        )

        # 5. Farmer Model
        await session.execute(
            insert(FarmerModel).values({
                "id": farmer_id,
                "user_id": farmer_user_id,
                "vlcc_id": vlcc_id,
                "farmer_code": "FARM-01",
                "milk_type": MilkType.COW,
                "created_by": vlcc_user_id,
                "created_at": today_dt,
                "updated_at": today_dt,
            })
        )

        # 6. Insert Collection (100 Ltr, FAT 4.0, SNF 8.5)
        await session.execute(
            insert(VlccCollectionModel).values({
                "id": uuid4(),
                "vlcc_id": vlcc_id,
                "farmer_id": farmer_id,
                "collected_at": today_dt,
                "shift": CollectionShift.MORNING,
                "milk_type": MilkType.COW,
                "fat_percent": Decimal("4.0"),
                "snf_percent": Decimal("8.5"),
                "quantity": Decimal("100.00"),
                "quantity_collection_mode": QuantityCollectionMode.MANUAL,
                "measurement_mode": MeasurementMode.MANUAL,
                "total_amount": Decimal("4000.00"),
                "is_deleted": False,
                "created_at": today_dt,
                "updated_at": today_dt,
            })
        )

        # 7. Insert Dispatch (95 Ltr, FAT 4.1, SNF 8.6, 2 Cans)
        await session.execute(
            insert(DispatchModel).values({
                "id": uuid4(),
                "vlcc_id": vlcc_id,
                "collected_at": today_dt,
                "shift": CollectionShift.MORNING,
                "fat_percent": Decimal("4.1"),
                "snf_percent": Decimal("8.6"),
                "quantity": Decimal("95.00"),
                "can_count": 2,
                "quantity_collection_mode": QuantityCollectionMode.MANUAL,
                "measurement_mode": MeasurementMode.MANUAL,
                "created_at": today_dt,
                "updated_at": today_dt,
            })
        )

    repo = DispatchRepository(database)
    handler = DispatchHandler(database=database, repository=repo)

    current_admin = CurrentUser(
        id=admin_id,
        role=str(Role.ADMIN.value),
    )

    # Test repository / handler get_comparison inside transaction
    async with database.transaction():
        items, summary = await handler.get_comparison(
            owner=current_admin,
            vlcc_id=vlcc_id,
            shift=CollectionShift.MORNING,
        )

    assert len(items) == 1
    item = items[0]
    assert item.vlcc_id == vlcc_id
    assert item.vlcc_name == "Green Dairy VLCC"
    assert item.shift == CollectionShift.MORNING
    assert item.collection_quantity == Decimal("100.00")
    assert item.dispatch_quantity == Decimal("95.00")
    assert item.quantity_diff == Decimal("-5.00")
    assert item.status == "SHORTAGE"
    assert item.dispatch_can_count == 2
    assert item.farmer_count == 1

    assert summary.total_collected_qty == Decimal("100.00")
    assert summary.total_dispatched_qty == Decimal("95.00")
    assert summary.net_variance_qty == Decimal("-5.00")
    assert summary.total_cans == 2
    assert summary.dispatch_ratio == 95.0


@pytest.mark.asyncio
async def test_dispatch_controller_list_page_tabs(database):
    admin_id = uuid4()
    current_admin = CurrentUser(
        id=admin_id,
        role=str(Role.ADMIN.value),
    )

    # Mock container and handlers
    repo = DispatchRepository(database)
    handler = DispatchHandler(database=database, repository=repo)
    mock_vlcc_handler = MagicMock()
    mock_vlcc_handler.list = AsyncMock(return_value=[])

    container_mock = MagicMock()
    def resolve_side_effect(target):
        if target is DispatchHandler:
            return handler
        from app.modules.vlcc.application.handler import VlccHandler
        if target is VlccHandler:
            return mock_vlcc_handler
        return MagicMock()

    container_mock.resolve.side_effect = resolve_side_effect

    # Mock Renderer.page to inspect model
    from unittest.mock import patch
    with patch("app.web.framework.renderer.Renderer.page", side_effect=lambda request, template, model: {"template": template, "model": model}) as mock_page:
        # 1. Comparison Tab
        req_comp = MagicMock()
        req_comp.state.user = current_admin
        req_comp.query_params = QueryParams({"tab": "comparison"})
        req_comp.app.state.application.container = container_mock

        async with database.transaction():
            res_comp = await DispatchController.list_page(request=req_comp, tab="comparison")
        
        assert res_comp["template"] == "pages/vlcc_dispatch/list.html"
        assert res_comp["model"]["active_tab"] == "comparison"
        assert "comparison_items" in res_comp["model"]
        assert "comparison_summary" in res_comp["model"]
        assert res_comp["model"]["start_date"] == now_naive_ist().strftime("%Y-%m-%d")
        assert res_comp["model"]["end_date"] == now_naive_ist().strftime("%Y-%m-%d")
        assert res_comp["model"]["today"] == now_naive_ist().strftime("%Y-%m-%d")

        # 2. Dispatches Tab
        req_disp = MagicMock()
        req_disp.state.user = current_admin
        req_disp.query_params = QueryParams({"tab": "dispatches"})
        req_disp.app.state.application.container = container_mock

        async with database.transaction():
            res_disp = await DispatchController.list_page(request=req_disp, tab="dispatches")
        
        assert res_disp["template"] == "pages/vlcc_dispatch/list.html"
        assert res_disp["model"]["active_tab"] == "dispatches"
        assert "items" in res_disp["model"]


def test_template_render_both_tabs():
    from pathlib import Path
    from starlette.templating import Jinja2Templates
    from starlette.requests import Request
    from app.modules.collections.vlcc_collection.domain.dispatch_dto import (
        ShiftComparisonItemDto,
        ComparisonSummaryDto,
    )

    template_dir = Path("app/web/templates")
    templates = Jinja2Templates(directory=str(template_dir))

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/vlcc-dispatches",
        "headers": [],
        "app": MagicMock(),
    }
    req = Request(scope)

    # 1. Test comparison tab render
    comp_item = ShiftComparisonItemDto(
        date=date.today(),
        shift=CollectionShift.MORNING,
        vlcc_id=uuid4(),
        vlcc_name="Test VLCC",
        collection_quantity=Decimal("150.00"),
        collection_fat=Decimal("4.2"),
        collection_snf=Decimal("8.6"),
        collection_count=10,
        farmer_count=8,
        dispatch_quantity=Decimal("148.50"),
        dispatch_fat=Decimal("4.2"),
        dispatch_snf=Decimal("8.6"),
        dispatch_can_count=3,
        dispatch_count=1,
        quantity_diff=Decimal("-1.50"),
        fat_diff=Decimal("0.0"),
        snf_diff=Decimal("0.0"),
        status="SHORTAGE",
    )
    summary = ComparisonSummaryDto(
        total_collected_qty=Decimal("150.00"),
        total_dispatched_qty=Decimal("148.50"),
        net_variance_qty=Decimal("-1.50"),
        total_cans=3,
        total_collections_count=10,
        avg_collection_fat=Decimal("4.2"),
        avg_collection_snf=Decimal("8.6"),
        avg_dispatch_fat=Decimal("4.2"),
        avg_dispatch_snf=Decimal("8.6"),
        dispatch_ratio=99.0,
    )

    ctx_comp = {
        "request": req,
        "current_user": CurrentUser(id=uuid4(), role=str(Role.ADMIN.value)),
        "active_tab": "comparison",
        "items": [],
        "comparison_items": [comp_item],
        "comparison_summary": summary,
        "total_comparison_count": 1,
        "vlccs": [],
        "selected_vlcc_id": None,
        "selected_shift": None,
        "start_date": None,
        "end_date": None,
        "page": 1,
        "limit": 20,
        "total_pages": 1,
    }
    rendered_comp = templates.get_template("pages/vlcc_dispatch/list.html").render(ctx_comp)
    assert "Collection Comparison" in rendered_comp
    assert "Test VLCC" in rendered_comp
    assert "150.00" in rendered_comp
    assert "148.50" in rendered_comp
    assert "In Stock / Short" in rendered_comp

    # 2. Test dispatches tab render
    ctx_disp = {
        "request": req,
        "current_user": CurrentUser(id=uuid4(), role=str(Role.ADMIN.value)),
        "active_tab": "dispatches",
        "items": [],
        "comparison_items": [],
        "comparison_summary": None,
        "total_comparison_count": 0,
        "vlccs": [],
        "selected_vlcc_id": None,
        "selected_shift": None,
        "start_date": None,
        "end_date": None,
        "page": 1,
        "limit": 10,
        "total_pages": 1,
    }
    rendered_disp = templates.get_template("pages/vlcc_dispatch/list.html").render(ctx_disp)
    assert "Dispatches" in rendered_disp
    assert "No Dispatches Found" in rendered_disp


