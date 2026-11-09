"""
Public store routes.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.web.storefront.cart_controller import CartController
from app.web.storefront.controller import StorefrontController as Controller

router = APIRouter(prefix="/marketplace", tags=["Web Store"], default_response_class=HTMLResponse)

router.add_api_route(path="", endpoint=Controller.home_page, methods=["GET"])
router.add_api_route(path="/", endpoint=Controller.home_page, methods=["GET"], include_in_schema=False)
router.add_api_route(path="/search", endpoint=Controller.search_page, methods=["GET"])
router.add_api_route(path="/products", endpoint=Controller.products_page, methods=["GET"])
router.add_api_route(path="/products/{slug}", endpoint=Controller.product_page, methods=["GET"])
router.add_api_route(path="/animals", endpoint=Controller.animals_page, methods=["GET"])
router.add_api_route(path="/animals/{slug}", endpoint=Controller.animal_page, methods=["GET"], name="animal_page")
router.add_api_route(path="/animals/{slug}/enquiry", endpoint=Controller.enquiry_post, methods=["POST"])
router.add_api_route(path="/policies/{key}", endpoint=Controller.policy_page, methods=["GET"])
router.add_api_route(path="/cart", endpoint=CartController.cart_page, methods=["GET"])
router.add_api_route(path="/cart/add", endpoint=CartController.add_to_cart, methods=["POST"])
router.add_api_route(path="/cart/update", endpoint=CartController.update_cart, methods=["POST"])
router.add_api_route(path="/checkout", endpoint=CartController.checkout_page, methods=["GET"])
router.add_api_route(path="/checkout", endpoint=CartController.checkout_post, methods=["POST"])
router.add_api_route(path="/order-placed/{order_ref}", endpoint=CartController.order_placed_page, methods=["GET"])
router.add_api_route(path="/track", endpoint=CartController.track_page, methods=["GET"])
router.add_api_route(path="/track", endpoint=CartController.track_post, methods=["POST"])
