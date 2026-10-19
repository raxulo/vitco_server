"""
VLCC Collection Web Routes
"""

from fastapi import APIRouter
from app.web.vlcc_collection.controller import VlccCollectionController


router = APIRouter(
    prefix="/vlcc-collections",
    tags=["VLCC Collection"],
)

router.add_api_route(
    "/create",
    VlccCollectionController.get_create_page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    VlccCollectionController.post_create_page,
    methods=["POST"],
)

router.add_api_route(
    "/edit/{collection_id}",
    VlccCollectionController.get_edit_page,
    methods=["GET"],
)

router.add_api_route(
    "/edit/{collection_id}",
    VlccCollectionController.post_update_page,
    methods=["POST"],
)

router.add_api_route(
    "/view/{collection_id}",
    VlccCollectionController.view_page,
    methods=["GET"],
)

router.add_api_route(
    "/delete/{collection_id}",
    VlccCollectionController.delete_post,
    methods=["POST"],
)

router.add_api_route(
    "/api/calculate-rate",
    VlccCollectionController.calculate_rate,
    methods=["GET"],
)

router.add_api_route(
    "/api/search-farmers",
    VlccCollectionController.search_farmers,
    methods=["GET"],
)

router.add_api_route(
    "/load-form",
    VlccCollectionController.load_form,
    methods=["GET"],
)

router.add_api_route(
    "",
    VlccCollectionController.page,
    methods=["GET"],
)
