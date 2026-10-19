from fastapi import APIRouter
from app.web.item.controller import ItemController

router = APIRouter(
    prefix="/items",
    tags=["Item Master"],
)

router.add_api_route(
    "/",
    ItemController.page,
    methods=["GET"],
)

router.add_api_route(
    "/add",
    ItemController.post_create,
    methods=["POST"],
)

router.add_api_route(
    "/edit/{id}",
    ItemController.post_edit,
    methods=["POST"],
)

router.add_api_route(
    "/delete/{id}",
    ItemController.post_delete,
    methods=["POST"],
)

router.add_api_route(
    "/validate-code",
    ItemController.validate_code,
    methods=["GET"],
)
