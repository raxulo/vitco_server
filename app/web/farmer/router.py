"""
Farmer Web Routes
"""

from fastapi import APIRouter
from app.web.farmer.controller import FarmerController


router = APIRouter(
    prefix="/farmer",
    tags=["Farmer"],
)

router.add_api_route(
    "",
    FarmerController.page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    FarmerController.get_create_page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    FarmerController.post_create_page,
    methods=["POST"],
)

router.add_api_route(
    "/edit/{farmer_id}",
    FarmerController.get_edit_page,
    methods=["GET"],
)

router.add_api_route(
    "/edit/{farmer_id}",
    FarmerController.post_update_page,
    methods=["POST"],
)

router.add_api_route(
    "/view/{farmer_id}",
    FarmerController.view_page,
    methods=["GET"],
)

router.add_api_route(
    "/delete/{id}",
    FarmerController.post_delete,
    methods=["POST"],
)

router.add_api_route(
    "/validation-code",
    FarmerController.validate_code,
    methods=["GET"],
)

router.add_api_route(
    "/api/ratecharts",
    FarmerController.get_rate_charts_options,
    methods=["GET"],
)
