"""
Managed Admins / Sub-admins Router
"""

from fastapi import APIRouter
from app.web.sub_admin.column_layout_controller import ColumnLayoutController
from app.web.sub_admin.controller import SubAdminController

router = APIRouter(tags=["Web SubAdmins"])

# Excel column order (Phase 24): before /sub-admins/{...} routes, own page for every manager
router.add_api_route(
    path="/sub-admins/column-layout",
    endpoint=ColumnLayoutController.page,
    methods=["GET"]
)

router.add_api_route(
    path="/sub-admins/column-layout",
    endpoint=ColumnLayoutController.save,
    methods=["POST"]
)

router.add_api_route(
    path="/sub-admins/column-layout/reset",
    endpoint=ColumnLayoutController.reset,
    methods=["POST"]
)

router.add_api_route(
    path="/sub-admins",
    endpoint=SubAdminController.list_page,
    methods=["GET"]
)

router.add_api_route(
    path="/sub-admins/create",
    endpoint=SubAdminController.create_page,
    methods=["GET"]
)

router.add_api_route(
    path="/sub-admins/create",
    endpoint=SubAdminController.create_post,
    methods=["POST"]
)

router.add_api_route(
    path="/sub-admins/delete/{user_id}",
    endpoint=SubAdminController.delete_post,
    methods=["POST"]
)

router.add_api_route(
    path="/sub-admins/validate-email",
    endpoint=SubAdminController.validate_email,
    methods=["GET"]
)

router.add_api_route(
    path="/sub-admins/view/{user_id}",
    endpoint=SubAdminController.view_page,
    methods=["GET"]
)

router.add_api_route(
    path="/sub-admins/edit/{user_id}",
    endpoint=SubAdminController.edit_page,
    methods=["GET"]
)

router.add_api_route(
    path="/sub-admins/edit/{user_id}",
    endpoint=SubAdminController.edit_post,
    methods=["POST"]
)
