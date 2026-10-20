"""
MCC Collection Web Routes
"""

from fastapi import APIRouter
from app.web.mcc_collection.controller import MccCollectionController


router = APIRouter(
    prefix="/mcc-collections",
    tags=["MCC Collection"],
)

router.add_api_route(
    "/create",
    MccCollectionController.get_create_page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    MccCollectionController.post_create_page,
    methods=["POST"],
)

router.add_api_route(
    "/edit/{collection_id}",
    MccCollectionController.get_edit_page,
    methods=["GET"],
)

router.add_api_route(
    "/edit/{collection_id}",
    MccCollectionController.post_update_page,
    methods=["POST"],
)

router.add_api_route(
    "/view/{collection_id}",
    MccCollectionController.view_page,
    methods=["GET"],
)

router.add_api_route(
    "/delete/{collection_id}",
    MccCollectionController.delete_post,
    methods=["POST"],
)

router.add_api_route(
    "/delete-bulk",
    MccCollectionController.delete_bulk_post,
    methods=["POST"],
)

router.add_api_route(
    "/validation-number",
    MccCollectionController.validate_number,
    methods=["GET"],
)

router.add_api_route(
    "/api/get-next-sample",
    MccCollectionController.get_next_sample,
    methods=["GET"],
)

router.add_api_route(
    "/api/search-sample",
    MccCollectionController.search_sample,
    methods=["GET"],
)

router.add_api_route(
    "/api/get-mcc-ratecharts",
    MccCollectionController.get_mcc_ratecharts,
    methods=["GET"],
)

router.add_api_route(
    "/api/calculate-rate",
    MccCollectionController.calculate_rate,
    methods=["GET"],
)

router.add_api_route(
    "/load-form",
    MccCollectionController.load_form,
    methods=["GET"],
)

router.add_api_route(
    "/get-sample-result",
    MccCollectionController.get_sample_result,
    methods=["GET"],
)


router.add_api_route(
    "",
    MccCollectionController.page,
    methods=["GET"],
)