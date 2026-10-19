from fastapi import APIRouter
from app.web.unit.controller import UnitController

router = APIRouter(
    prefix="/units",
    tags=["Unit Master"],
)

router.add_api_route(
    "/",
    UnitController.page,
    methods=["GET"],
)

router.add_api_route(
    "/add",
    UnitController.post_create,
    methods=["POST"],
)

router.add_api_route(
    "/edit/{id}",
    UnitController.post_edit,
    methods=["POST"],
)

router.add_api_route(
    "/delete/{id}",
    UnitController.post_delete,
    methods=["POST"],
)
