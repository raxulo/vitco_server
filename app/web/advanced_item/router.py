from fastapi import APIRouter
from app.web.advanced_item.controller import AdvancedItemController

router = APIRouter(
    prefix="/advance-items",
    tags=["Advance Items"],
)

router.add_api_route(
    "/",
    AdvancedItemController.list_page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    AdvancedItemController.create_page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    AdvancedItemController.post_create,
    methods=["POST"],
)

router.add_api_route(
    "/view/{id}",
    AdvancedItemController.view_page,
    methods=["GET"],
)
