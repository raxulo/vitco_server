"""
RateChart Web Routes
"""

from fastapi import APIRouter
from app.web.ratechart.controller import RateChartController


router = APIRouter(
    prefix="/ratecharts",
    tags=["Rate Chart"],
)

router.add_api_route(
    "/add",
    RateChartController.get_create_page,
    methods=["GET"],
)

router.add_api_route(
    "/add",
    RateChartController.post_create_page,
    methods=["POST"],
)

router.add_api_route(
    "/edit/{chart_id}",
    RateChartController.get_edit_page,
    methods=["GET"],
)

router.add_api_route(
    "/edit/{chart_id}",
    RateChartController.post_update_page,
    methods=["POST"],
)

router.add_api_route(
    "/view/{chart_id}",
    RateChartController.view_page,
    methods=["GET"],
)

router.add_api_route(
    "/delete/{chart_id}",
    RateChartController.delete_post,
    methods=["POST"],
)

router.add_api_route(
    "/assign",
    RateChartController.assign_page,
    methods=["GET"],
)

router.add_api_route(
    "/assign-mcc",
    RateChartController.assign_mcc_page,
    methods=["GET"],
)

router.add_api_route(
    "/api/assign-mcc/load-boxes",
    RateChartController.load_mcc_boxes,
    methods=["GET"],
)

router.add_api_route(
    "/api/assign-vlcc/load-boxes",
    RateChartController.load_vlcc_boxes,
    methods=["GET"],
)

router.add_api_route(
    "/api/assigned",
    RateChartController.get_assigned_api,
    methods=["GET"],
)

router.add_api_route(
    "/api/assigned-mcc",
    RateChartController.get_assigned_mcc_api,
    methods=["GET"],
)

router.add_api_route(
    "/api/assign-bulk",
    RateChartController.post_assign_bulk_api,
    methods=["POST"],
)

router.add_api_route(
    "/api/assign-mcc-bulk",
    RateChartController.post_assign_mcc_bulk_api,
    methods=["POST"],
)

router.add_api_route(
    "/get-rate",
    RateChartController.calculate_rate,
    methods=["GET"],
)

router.add_api_route(
    "",
    RateChartController.page,
    methods=["GET"],
)
