"""
Unit tests for VLCC_FARMER (Role 7) permissions, navigation, dashboard, and controller restrictions.
"""
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.requests import Request

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.dashboard.presentation.navigation import build_navigation
from app.web.framework.helpers import WebHelper
from app.core.exceptions.base import ForbiddenException
from app.modules.dashboard.application.command import GetDashboardQuery
from app.modules.dashboard.application.handler import DashboardHandler
from app.modules.dashboard.application.dto import CollectionTotals
from app.modules.dashboard.domain.enums import DashboardPeriod
from app.web.mcc_collection.controller import MccCollectionController
from app.web.vlcc_collection.controller import VlccCollectionController
from app.web.payments.controller import PaymentsController
from app.web.reports.controller import ReportsController
from app.web.route.controller import RouteController
from app.web.unit.controller import UnitController
from app.web.item.controller import ItemController
from app.web.advanced_item.controller import AdvancedItemController
from app.web.ratechart.controller import RateChartController
from app.web.vlcc_dispatch.controller import DispatchController
from app.web.vlcc.controller import VlccController
from app.web.farmer.controller import FarmerController
from app.web.mcc.controller import MccController


def make_request(user: CurrentUser) -> Request:
    req = Request({"type": "http"})
    req.state.user = user
    return req


def test_current_user_is_farmer_vlcc():
    uid = uuid4()
    
    # 1. Normal VLCC
    normal_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC)))
    assert not normal_vlcc.is_farmer_vlcc
    
    # 2. VLCC Farmer (Role 7)
    farmer_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC_FARMER)))
    assert farmer_vlcc.is_farmer_vlcc
    assert farmer_vlcc.role_type == Role.VLCC_FARMER
    
    # 3. Regular Farmer
    farmer_role = CurrentUser(id=uid, role=str(int(Role.FARMER)))
    assert not farmer_role.is_farmer_vlcc
    
    # 4. Admin
    admin_role = CurrentUser(id=uid, role=str(int(Role.ADMIN)))
    assert not admin_role.is_farmer_vlcc


def test_build_navigation_for_farmer_vlcc():
    # 1. Farmer VLCC navigation (using Role.VLCC_FARMER directly)
    nav = build_navigation(int(Role.VLCC_FARMER))
    assert len(nav) == 1
    assert nav[0].label == "General"
    item_labels = [item.label for item in nav[0].items]
    assert item_labels == ["Dashboard", "My Collections", "My Payments"]
    
    # Check hrefs
    assert nav[0].items[0].href == "/dashboard"
    assert nav[0].items[1].href == "/mcc-collections/"
    assert nav[0].items[2].href == "/payments/history"
    
    # Also via is_farmer_vlcc kwarg
    nav_kwarg = build_navigation(int(Role.VLCC), is_farmer_vlcc=True)
    assert [item.label for item in nav_kwarg[0].items] == ["Dashboard", "My Collections", "My Payments"]
    
    # 2. Normal VLCC navigation
    nav_normal = build_navigation(int(Role.VLCC), is_farmer_vlcc=False)
    group_labels = [group.label for group in nav_normal]
    assert "VLCC Management" in group_labels
    assert "System Setup" in group_labels
    assert "Payments" in group_labels


def test_web_helper_deny_farmer_vlcc():
    uid = uuid4()
    farmer_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC_FARMER)))
    normal_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC)))
    
    req_farmer_vlcc = make_request(farmer_vlcc)
    req_normal_vlcc = make_request(normal_vlcc)
    
    # Farmer VLCC should be denied
    with pytest.raises(ForbiddenException):
        WebHelper.deny_farmer_vlcc(req_farmer_vlcc)
        
    # Normal VLCC should be allowed
    WebHelper.deny_farmer_vlcc(req_normal_vlcc)


def test_mcc_collection_deny_vlcc():
    uid = uuid4()
    farmer_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC_FARMER)))
    normal_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC)))
    mcc_user = CurrentUser(id=uid, role=str(int(Role.MCC)))
    
    req_f_vlcc = make_request(farmer_vlcc)
    req_n_vlcc = make_request(normal_vlcc)
    req_mcc = make_request(mcc_user)
    
    # Both VLCC types cannot create/edit/delete MCC collection
    with pytest.raises(ForbiddenException):
        MccCollectionController._deny_vlcc(req_f_vlcc)
        
    with pytest.raises(ForbiddenException):
        MccCollectionController._deny_vlcc(req_n_vlcc)
        
    # MCC user is allowed
    MccCollectionController._deny_vlcc(req_mcc)


def test_vlcc_collection_deny_farmer_and_farmer_vlcc():
    uid = uuid4()
    farmer_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC_FARMER)))
    normal_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC)))
    farmer_user = CurrentUser(id=uid, role=str(int(Role.FARMER)))
    
    req_f_vlcc = make_request(farmer_vlcc)
    req_farmer = make_request(farmer_user)
    req_n_vlcc = make_request(normal_vlcc)
    
    # Both Farmer and VLCC_FARMER are denied on VLCC collection entry
    with pytest.raises(ForbiddenException):
        VlccCollectionController._deny_farmer(req_f_vlcc)
        
    with pytest.raises(ForbiddenException):
        VlccCollectionController._deny_farmer(req_farmer)
        
    # Normal VLCC is allowed
    VlccCollectionController._deny_farmer(req_n_vlcc)


@pytest.mark.asyncio
async def test_vlcc_collection_page_redirects_for_farmer_vlcc():
    uid = uuid4()
    farmer_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC_FARMER)))
    req = make_request(farmer_vlcc)
    
    res = await VlccCollectionController.page(req)
    assert res.headers.get("location") == "/mcc-collections/"


@pytest.mark.asyncio
async def test_dashboard_handler_for_farmer_vlcc():
    uid = uuid4()
    farmer_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC_FARMER)), name="Farmer Dairy")
    
    mock_repo = MagicMock()
    source_mock = MagicMock()
    mock_repo.mcc_collections.return_value = source_mock
    mock_repo.vlcc_collections.return_value = MagicMock()
    
    totals = CollectionTotals(
        quantity=150.0,
        amount=5400.0,
        fat_qty=6.0,
        snf_qty=12.0,
        entries=5,
        parties=1,
        days=3,
    )
    mock_repo.totals = AsyncMock(return_value=totals)
    mock_repo.daily = AsyncMock(return_value={})
    mock_repo.quantity_by = AsyncMock(return_value={})
    mock_repo.recent = AsyncMock(return_value=())
    mock_repo.scope_label = AsyncMock(return_value="Farmer Dairy")
    
    handler = DashboardHandler(mock_repo)
    query = GetDashboardQuery(owner=farmer_vlcc, period=DashboardPeriod.MONTH)
    
    result = await handler.get_dashboard(query)
    
    # Verify source was mcc_collections, NOT vlcc_collections
    mock_repo.mcc_collections.assert_called_once_with(farmer_vlcc)
    
    # Verify role_label
    assert result.role_label == "VLCC (Farmer)"
    
    # Verify KPIs match Farmer-style
    kpi_labels = [kpi.label for kpi in result.kpis]
    assert kpi_labels == ["Milk Poured", "Earnings", "Days Poured", "Entries"]
    
    # Verify leaderboard is empty
    assert result.leaderboard_title == ""
    assert result.leaderboard == ()
    
    # Verify quick actions
    assert len(result.quick_actions) == 2
    assert result.quick_actions[0].href == "/mcc-collections/"
    assert result.quick_actions[1].href == "/payments/history"


@pytest.mark.asyncio
async def test_system_setup_and_masters_denied_for_farmer_vlcc():
    uid = uuid4()
    farmer_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC_FARMER)))
    req = make_request(farmer_vlcc)
    
    # 1. Routes
    with pytest.raises(ForbiddenException):
        await RouteController.page(req)
        
    # 2. Units
    with pytest.raises(ForbiddenException):
        await UnitController.page(req)
        
    # 3. Items
    with pytest.raises(ForbiddenException):
        await ItemController.page(req)
        
    # 4. Advance Items
    with pytest.raises(ForbiddenException):
        await AdvancedItemController.list_page(req)
        
    # 5. Rate Charts
    with pytest.raises(ForbiddenException):
        await RateChartController.page(req)
        
    # 6. Dispatches
    with pytest.raises(ForbiddenException):
        await DispatchController.list_page(req)
        
    # 7. VLCC Master
    with pytest.raises(ForbiddenException):
        await VlccController.list_page(req)
        
    # 8. Reports
    with pytest.raises(ForbiddenException):
        await ReportsController.page(req)
    with pytest.raises(ForbiddenException):
        await ReportsController.vlcc_page(req)
        
    # 9. Payment Give / Receive
    with pytest.raises(ForbiddenException):
        await PaymentsController.give_receive_page(req)
    with pytest.raises(ForbiddenException):
        await PaymentsController.post_give_receive(req)

    # 10. Farmer controller denied
    with pytest.raises(ForbiddenException):
        await FarmerController.page(req)
    with pytest.raises(ForbiddenException):
        await FarmerController.get_create_page(req)
    with pytest.raises(ForbiddenException):
        await FarmerController.post_create_page(req)
    with pytest.raises(ForbiddenException):
        await FarmerController.post_update_page(req, farmer_id=uuid4())
    with pytest.raises(ForbiddenException):
        await FarmerController.delete_post(req, farmer_id=uuid4())

    # 11. MCC Master denied
    with pytest.raises(ForbiddenException):
        await MccController.page(req)

    # 12. VLCC create/edit denied
    with pytest.raises(ForbiddenException):
        await VlccController.create_page(req)
    with pytest.raises(ForbiddenException):
        await VlccController.create(req)
    with pytest.raises(ForbiddenException):
        await VlccController.update(req, vlcc_id=uuid4())
    with pytest.raises(ForbiddenException):
        await VlccController.post_delete(req, id=uuid4())


@pytest.mark.asyncio
async def test_sync_api_for_farmer_vlcc():
    from unittest.mock import patch
    from app.api.v1.routers.sync import vlcc_data
    
    uid = uuid4()
    vid = uuid4()
    farmer_vlcc = CurrentUser(id=uid, role=str(int(Role.VLCC_FARMER)), own_id=vid, name="Farmer Dairy")
    
    req = MagicMock()
    mock_detail = MagicMock()
    mock_detail.vlcc = MagicMock(id=vid, user_id=uid, vlcc_code="VFM01", uic_code="U01", profile_image=None, route_code=None, entry_mode=1, soc_percentage=0, farmer_enabled=True)
    mock_detail.user = MagicMock(name="Farmer Dairy", email="vfm@test.com", mobile="9876543210", profile_image=None)
    mock_detail.bank_account = None
    mock_detail.address = None
    mock_detail.setting = None
    mock_detail.milk_quality_config = None
    
    mock_vlcc_handler = MagicMock()
    mock_vlcc_handler.get_full_detail = AsyncMock(return_value=mock_detail)
    
    with patch("app.api.v1.routers.sync.GetHandler.vlcc_handler", return_value=mock_vlcc_handler), \
         patch("app.api.v1.routers.sync.fetch_all_ratecharts", AsyncMock(return_value=[])):
        sync_dto = await vlcc_data(req, farmer_vlcc)
        
        assert sync_dto.role == Role.VLCC_FARMER
        assert sync_dto.profile.role == Role.VLCC_FARMER
        assert sync_dto.sub_users == []
        assert sync_dto.vlcc_info.farmer_enabled is False


def test_vlcc_type_int_enum_definition():
    from app.modules.vlcc.domain.enums import VlccType
    assert issubclass(VlccType, int)
    assert VlccType.NORMAL == 0
    assert VlccType.VLCC_FARMER_TYPE == 1
    assert VlccType(0) == VlccType.NORMAL
    assert VlccType(1) == VlccType.VLCC_FARMER_TYPE
    assert VlccType.NORMAL.label == "Normal"
    assert VlccType.VLCC_FARMER_TYPE.label == "VLCC Farmer Type"


def test_vlcc_mapper_parse_vlcc_type():
    from app.modules.vlcc.infrastructure.mapper import VlccMapper
    from app.modules.vlcc.domain.enums import VlccType

    assert VlccMapper._parse_vlcc_type(0) == VlccType.NORMAL
    assert VlccMapper._parse_vlcc_type(1) == VlccType.VLCC_FARMER_TYPE
    assert VlccMapper._parse_vlcc_type("0") == VlccType.NORMAL
    assert VlccMapper._parse_vlcc_type("1") == VlccType.VLCC_FARMER_TYPE
    assert VlccMapper._parse_vlcc_type("NORMAL") == VlccType.NORMAL
    assert VlccMapper._parse_vlcc_type("VLCC_FARMER_TYPE") == VlccType.VLCC_FARMER_TYPE
    assert VlccMapper._parse_vlcc_type(None) == VlccType.NORMAL


def test_vlcc_request_validation():
    from app.modules.vlcc.presentation.requests import CreateVlccRequest
    from app.modules.vlcc.domain.enums import VlccType

    assert CreateVlccRequest._validate_vlcc_type(0) == VlccType.NORMAL
    assert CreateVlccRequest._validate_vlcc_type(1) == VlccType.VLCC_FARMER_TYPE
    assert CreateVlccRequest._validate_vlcc_type("0") == VlccType.NORMAL
    assert CreateVlccRequest._validate_vlcc_type("1") == VlccType.VLCC_FARMER_TYPE
    assert CreateVlccRequest._validate_vlcc_type("NORMAL") == VlccType.NORMAL
    assert CreateVlccRequest._validate_vlcc_type("VLCC_FARMER_TYPE") == VlccType.VLCC_FARMER_TYPE
