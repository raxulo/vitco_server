import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from sqlalchemy import insert
from starlette.datastructures import QueryParams

from app.core.clock import now_naive_ist
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.vlcc.infrastructure.models import VlccModel
from app.middleware.authentication import CurrentUser
from app.web.payments.controller import PaymentsController


@pytest.mark.asyncio
async def test_outstanding_page_filter_admin_and_role_restrictions(database):
    admin_id = uuid4()
    subadmin_id = uuid4()
    mcc_user_id = uuid4()
    mcc_id = uuid4()
    outsider_user_id = uuid4()
    outsider_mcc_id = uuid4()
    vlcc_user_id = uuid4()
    vlcc_id = uuid4()

    async with database.transaction() as session:
        # 1. Admin user
        await session.execute(
            insert(UserModel).values([
                {
                    "id": admin_id,
                    "name": "Main Admin",
                    "email": f"admin-{admin_id.hex[:6]}@test.local",
                    "mobile": f"9{str(admin_id.int)[-9:]}",
                    "password_hash": "hash",
                    "role": Role.ADMIN,
                    "created_by": None,
                    "created_at": now_naive_ist(),
                    "updated_at": now_naive_ist(),
                },
                # 2. SubAdmin created by Admin
                {
                    "id": subadmin_id,
                    "name": "Sub Admin 1",
                    "email": f"sub-{subadmin_id.hex[:6]}@test.local",
                    "mobile": f"9{str(subadmin_id.int)[-9:]}",
                    "password_hash": "hash",
                    "role": Role.SUB_ADMIN,
                    "created_by": admin_id,
                    "created_at": now_naive_ist(),
                    "updated_at": now_naive_ist(),
                },
                # 3. MCC User
                {
                    "id": mcc_user_id,
                    "name": "MCC Center User",
                    "email": f"mcc-{mcc_user_id.hex[:6]}@test.local",
                    "mobile": f"9{str(mcc_user_id.int)[-9:]}",
                    "password_hash": "hash",
                    "role": Role.MCC,
                    "created_by": subadmin_id,
                    "created_at": now_naive_ist(),
                    "updated_at": now_naive_ist(),
                },
                # 4. Outsider User & outsider MCC (independent user)
                {
                    "id": outsider_user_id,
                    "name": "Outsider MCC User",
                    "email": f"out-{outsider_user_id.hex[:6]}@test.local",
                    "mobile": f"9{str(outsider_user_id.int)[-9:]}",
                    "password_hash": "hash",
                    "role": Role.MCC,
                    "created_by": None,
                    "created_at": now_naive_ist(),
                    "updated_at": now_naive_ist(),
                },
                # 5. VLCC User
                {
                    "id": vlcc_user_id,
                    "name": "VLCC Center User",
                    "email": f"vlcc-{vlcc_user_id.hex[:6]}@test.local",
                    "mobile": f"9{str(vlcc_user_id.int)[-9:]}",
                    "password_hash": "hash",
                    "role": Role.VLCC,
                    "created_by": mcc_user_id,
                    "created_at": now_naive_ist(),
                    "updated_at": now_naive_ist(),
                },
            ])
        )

        # Insert MCC under SubAdmin
        await session.execute(
            insert(MccModel).values({
                "id": mcc_id,
                "user_id": mcc_user_id,
                "code": "MCC-001",
                "name": "SubAdmin MCC Center",
                "created_by": subadmin_id,
                "is_deleted": False,
                "created_at": now_naive_ist(),
                "updated_at": now_naive_ist(),
            })
        )

        # Insert Outsider MCC under outsider user
        await session.execute(
            insert(MccModel).values({
                "id": outsider_mcc_id,
                "user_id": outsider_user_id,
                "code": "MCC-OUT",
                "name": "Foreign MCC Center",
                "created_by": outsider_user_id,
                "is_deleted": False,
                "created_at": now_naive_ist(),
                "updated_at": now_naive_ist(),
            })
        )

        # Insert VLCC under MCC user
        await session.execute(
            insert(VlccModel).values({
                "id": vlcc_id,
                "user_id": vlcc_user_id,
                "vlcc_code": "VLCC-001",
                "uic_code": "UIC-001",
                "name": "SubAdmin VLCC Center",
                "created_by": mcc_user_id,
                "is_deleted": False,
                "created_at": now_naive_ist(),
                "updated_at": now_naive_ist(),
            })
        )

    # Mock service & app state
    mock_service = MagicMock()
    mock_service.get_user_outstanding = MagicMock()

    async def fake_get_outstanding(user_id):
        return []

    mock_service.get_user_outstanding.side_effect = fake_get_outstanding

    def create_mock_request(user: CurrentUser, query_params: dict = None):
        req = MagicMock()
        req.state.user = user
        req.query_params = QueryParams(query_params or {})
        req.app.state.application.container.database = database
        return req

    # Patch GetHandler to return our mock service
    from unittest.mock import patch
    with patch("app.modules.dependencies.GetHandler.payment_posting_service", return_value=mock_service):
        with patch("app.web.framework.renderer.Renderer.page", side_effect=lambda request, template, model: model) as mock_render:
            async with database.transaction():
                # 1. Admin login without filter -> can_filter=True, lists MCC and VLCC, target_user_id=admin_id
                admin_user = CurrentUser(
                    id=admin_id,
                    role=Role.ADMIN.value,
                    name="Main Admin",
                )
                req1 = create_mock_request(admin_user)
                model1 = await PaymentsController.outstanding_page(req1)

                assert model1["can_filter"] is True
                mcc_user_ids = [m["user_id"] for m in model1["mccs"]]
                vlcc_user_ids = [v["user_id"] for v in model1["vlccs"]]
                assert str(mcc_user_id) in mcc_user_ids
                assert str(vlcc_user_id) in vlcc_user_ids
                assert str(outsider_user_id) not in mcc_user_ids
                assert model1["target_user_id"] == str(admin_id)

                # 2. Admin selecting MCC -> target_user_id becomes mcc_user_id
                req2 = create_mock_request(admin_user, {"user_id": str(mcc_user_id)})
                model2 = await PaymentsController.outstanding_page(req2)
                assert model2["selected_user_id"] == str(mcc_user_id)
                assert model2["target_user_id"] == str(mcc_user_id)
                assert model2["selected_entity"]["name"] == "SubAdmin MCC Center"

                # 3. Admin attempting to select outsider MCC -> falls back to admin_id
                req3 = create_mock_request(admin_user, {"user_id": str(outsider_user_id)})
                model3 = await PaymentsController.outstanding_page(req3)
                assert model3["selected_user_id"] == ""
                assert model3["target_user_id"] == str(admin_id)

                # 4. VLCC user login -> can_filter=False, empty mccs/vlccs, target_user_id=vlcc_user_id
                vlcc_user = CurrentUser(
                    id=vlcc_user_id,
                    role=Role.VLCC.value,
                    name="VLCC Center User",
                )
                # Even if VLCC passes ?user_id=<mcc_user_id>, it must be ignored completely
                req4 = create_mock_request(vlcc_user, {"user_id": str(mcc_user_id)})
                model4 = await PaymentsController.outstanding_page(req4)
                assert model4["can_filter"] is False
                assert model4["mccs"] == []
                assert model4["vlccs"] == []
                assert model4["selected_user_id"] == ""
                assert model4["target_user_id"] == str(vlcc_user_id)

                # 5. Test search_centers_api for Admin (Search by name / code)
                req_search_admin = create_mock_request(admin_user, {"q": "MCC-001"})
                res_search_admin = await PaymentsController.search_centers_api(req_search_admin, q="MCC-001")
                import json
                search_data = json.loads(res_search_admin.body.decode("utf-8"))
                found_center_ids = [c["user_id"] for c in search_data["centers"]]
                assert str(mcc_user_id) in found_center_ids
                assert str(outsider_user_id) not in found_center_ids

                # 6. Test search_centers_api for unauthorized role (VLCC) -> empty
                req_search_vlcc = create_mock_request(vlcc_user, {"q": "MCC"})
                res_search_vlcc = await PaymentsController.search_centers_api(req_search_vlcc, q="MCC")
                vlcc_search_data = json.loads(res_search_vlcc.body.decode("utf-8"))
                assert vlcc_search_data["centers"] == []
