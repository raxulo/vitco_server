from fastapi import APIRouter
from app.web.route.controller import RouteController

router = APIRouter(
    prefix="/routes",
    tags=["Route Master"],
)

router.add_api_route(
    "/",
    RouteController.page,
    methods=["GET"],
)

router.add_api_route(
    "/add",
    RouteController.post_create,
    methods=["POST"],
)

router.add_api_route(
    "/edit/{id}",
    RouteController.post_edit,
    methods=["POST"],
)

router.add_api_route(
    "/delete/{id}",
    RouteController.post_delete,
    methods=["POST"],
)

router.add_api_route(
    "/validate-code",
    RouteController.validate_code,
    methods=["GET"],
)
