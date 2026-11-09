"""
Marketplace Control Center routes (DECISION-019: outside the public /marketplace prefix).
"""

from fastapi import APIRouter, Depends

from app.web.marketplace_admin.controller import MarketplaceAdminController as Controller
from app.web.marketplace_admin.controller import load_waiting_counts
from app.web.marketplace_admin.merchandising_controller import MerchandisingController as Merchandising
from app.web.marketplace_admin.order_controller import OrderController

router = APIRouter(
    prefix="/admin/marketplace",
    tags=["Web Marketplace Control Center"],
    dependencies=[Depends(load_waiting_counts)],
)

_ROUTES = (
    ("", Controller.overview_page, "GET"),
    ("/products", Controller.products_page, "GET"),
    ("/products/new", Controller.product_new_page, "GET"),
    ("/products/new", Controller.product_create, "POST"),
    ("/products/{product_id}", Controller.product_edit_page, "GET"),
    ("/products/{product_id}", Controller.product_update, "POST"),
    ("/products/{product_id}/delete", Controller.product_delete, "POST"),
    ("/animals", Controller.animals_page, "GET"),
    ("/animals/new", Controller.animal_new_page, "GET"),
    ("/animals/new", Controller.animal_create, "POST"),
    ("/animals/{animal_id}", Controller.animal_edit_page, "GET"),
    ("/animals/{animal_id}", Controller.animal_update, "POST"),
    ("/animals/{animal_id}/delete", Controller.animal_delete, "POST"),
    ("/orders", OrderController.orders_page, "GET"),
    ("/orders/{order_id}", OrderController.order_page, "GET"),
    ("/orders/{order_id}/move", OrderController.order_move, "POST"),
    ("/enquiries", Controller.enquiries_page, "GET"),
    ("/enquiries/{enquiry_id}", Controller.enquiry_update, "POST"),
    ("/categories", Controller.categories_page, "GET"),
    ("/categories", Controller.category_save, "POST"),
    ("/categories/{category_id}/delete", Controller.category_delete, "POST"),
    ("/animal-types", Controller.animal_types_page, "GET"),
    ("/animal-types", Controller.animal_type_save, "POST"),
    ("/animal-types/{animal_type_id}/delete", Controller.animal_type_delete, "POST"),
    ("/animal-breeds", Controller.animal_breed_save, "POST"),
    ("/animal-breeds/{breed_id}/delete", Controller.animal_breed_delete, "POST"),
    ("/banners", Merchandising.banners_page, "GET"),
    ("/banners", Merchandising.banner_save, "POST"),
    ("/banners/{banner_id}/delete", Merchandising.banner_delete, "POST"),
    ("/home", Merchandising.home_page, "GET"),
    ("/home-sections", Merchandising.section_save, "POST"),
    ("/home-sections/{section_id}/move", Merchandising.section_move, "POST"),
    ("/home-sections/{section_id}/delete", Merchandising.section_delete, "POST"),
    ("/trending", Merchandising.tag_save, "POST"),
    ("/trending/{tag_id}/delete", Merchandising.tag_delete, "POST"),
    ("/settings", Merchandising.settings_page, "GET"),
    ("/settings", Merchandising.settings_save, "POST"),
)

for path, endpoint, method in _ROUTES:
    router.add_api_route(path=path, endpoint=endpoint, methods=[method])
