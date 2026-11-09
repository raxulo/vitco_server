"""
Marketplace Control Center pages.

Forms are plain multipart POSTs: success redirects with 303, a validation problem shows
the form again (422) with a message per field and what the user typed.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from starlette.datastructures import FormData, UploadFile
from starlette.responses import RedirectResponse, Response

from app.core.exceptions.base import ForbiddenException
from app.modules.administration.domain.enums import Role
from app.modules.dependencies import GetHandler
from app.modules.marketplace.application.command import (
    SaveAnimalBreedCommand,
    SaveAnimalCommand,
    SaveAnimalTypeCommand,
    SaveCategoryCommand,
    SaveProductCommand,
    UpdateEnquiryCommand,
    VariantInput,
)
from app.modules.marketplace.application.handler import MAX_LISTING_IMAGES
from app.modules.marketplace.domain.entities import Animal, Category, ListingImage, Product
from app.modules.marketplace.domain.enums import (
    AnimalGender,
    AnimalStatus,
    EnquiryStatus,
    PregnancyStatus,
    ProductStatus,
)
from app.modules.marketplace.domain.exceptions import (
    AnimalBreedNotFoundException,
    AnimalNotFoundException,
    AnimalTypeNotFoundException,
    CategoryNotFoundException,
    EnquiryNotFoundException,
    ListingValidationException,
    MasterInUseException,
    ProductNotFoundException,
)
from app.modules.marketplace.domain.policy import SellerPolicy
from app.modules.marketplace.presentation.requests import (
    AnimalBreedForm,
    AnimalForm,
    AnimalTypeForm,
    CategoryForm,
    EnquiryUpdateForm,
    ProductForm,
    parse_form,
)
from app.web.framework.renderer import Renderer

_BASE = "/admin/marketplace"
_PAGE_SIZE = 20
_NOTICES = {
    "created": "Saved.",
    "saved": "Changes saved.",
    "deleted": "Deleted.",
}
_NOT_FOUND = (
    AnimalBreedNotFoundException,
    AnimalNotFoundException,
    AnimalTypeNotFoundException,
    CategoryNotFoundException,
    ProductNotFoundException,
)


def _done(path: str, notice: str) -> RedirectResponse:
    return RedirectResponse(url=f"{_BASE}{path}?done={notice}", status_code=303)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Not found")


_LATEST_ORDERS = 5


def _seller(request: Request):
    user = getattr(request.state, "user", None)
    if user is None or not SellerPolicy.can_sell(user.role_type):
        raise ForbiddenException("You do not have access to the Marketplace Control Center")
    return user


def _super_admin(request: Request):
    user = _seller(request)
    if user.role_type != Role.SUPER_ADMIN:
        raise ForbiddenException("Only the Super Admin can change categories and animal types")
    return user


async def load_waiting_counts(request: Request) -> None:
    """Runs before every Control Center route, so each page's tabs can show what is waiting."""
    user = getattr(request.state, "user", None)
    if user is None or not SellerPolicy.can_sell(user.role_type):
        return  # the route itself refuses this visitor
    request.state.mk_waiting = await GetHandler.marketplace_catalog_handler(request).waiting_counts(user)


def _page(request: Request, template: str, section: str, model: dict[str, Any], status_code: int = 200) -> Response:
    user = _seller(request)
    return Renderer.page(
        request=request,
        template=f"pages/marketplace_admin/{template}",
        model={
            "section": section,
            "can_edit_masters": user.role_type == Role.SUPER_ADMIN,
            "notice": _NOTICES.get(request.query_params.get("done", "")),
            **model,
        },
        status_code=status_code,
    )


def _pagination(total: int, page: int) -> dict[str, int]:
    return {
        "page": page,
        "total": total,
        "total_pages": max((total + _PAGE_SIZE - 1) // _PAGE_SIZE, 1),
    }


def _uploads(form: FormData, name: str) -> list[UploadFile]:
    return [item for item in form.getlist(name) if isinstance(item, UploadFile) and item.filename]


def _upload(form: FormData, name: str) -> UploadFile | None:
    item = form.get(name)
    return item if isinstance(item, UploadFile) and item.filename else None


def _text_fields(form: FormData, names: tuple[str, ...]) -> dict[str, Any]:
    return {name: str(form[name]) for name in names if name in form and not isinstance(form[name], UploadFile)}


def _parse_choice[T](kind: type[T], value: str) -> T | None:
    """An enum member or UUID from text; anything else counts as not chosen."""
    try:
        return kind(value)
    except ValueError:
        return None


# =========================================================
# FORM VALUES
# =========================================================

_PRODUCT_FIELDS = (
    "category_id", "title", "brand", "short_description", "description", "status",
    "is_featured", "is_trending", "sort_order",
)
_ANIMAL_FIELDS = (
    "animal_type_id", "breed_id", "title", "gender", "price", "is_negotiable", "age_months", "lactation_number",
    "milk_litres_per_day", "fat_percent", "pregnancy_status", "pregnancy_months", "calf_details", "health_notes",
    "vaccination_notes", "state", "district", "village", "description", "status", "is_featured", "is_trending",
    "sort_order",
)


def _product_data(form: FormData) -> dict[str, Any]:
    """Repeated form fields to rows. A row left completely blank is ignored."""
    default_row = str(form.get("variant_default", ""))
    variants = []
    columns = zip(
        form.getlist("variant_id"), form.getlist("variant_name"), form.getlist("variant_sku"),
        form.getlist("variant_mrp"), form.getlist("variant_price"), form.getlist("variant_stock"),
        form.getlist("variant_low_stock"), form.getlist("variant_active"), form.getlist("variant_row"),
        strict=False,
    )
    for row_id, name, sku, mrp, price, stock, low_stock, active, row in columns:
        if not any(str(value).strip() for value in (name, sku, mrp, price, stock)):
            continue
        variants.append({
            "id": row_id, "name": str(name).strip(), "sku": sku, "mrp": mrp, "price": price, "stock": stock,
            "low_stock_threshold": low_stock, "is_active": active, "is_default": str(row) == default_row,
        })
    specifications = [
        {"label": str(label).strip(), "value": str(value).strip()}
        for label, value in zip(form.getlist("spec_label"), form.getlist("spec_value"), strict=False)
        if str(label).strip() and str(value).strip()
    ]
    return {
        **_text_fields(form, _PRODUCT_FIELDS),
        "variants": variants,
        "specifications": specifications,
        "keep_image_ids": [str(value) for value in form.getlist("keep_image_id")],
    }


def _animal_data(form: FormData) -> dict[str, Any]:
    return {
        **_text_fields(form, _ANIMAL_FIELDS),
        "keep_image_ids": [str(value) for value in form.getlist("keep_image_id")],
    }


def _product_values(product: Product) -> dict[str, Any]:
    values = asdict(product)
    values["status"] = product.status.value
    return values


def _animal_values(animal: Animal) -> dict[str, Any]:
    values = asdict(animal)
    for name in ("status", "gender", "pregnancy_status"):
        values[name] = getattr(animal, name).value
    return values


def _kept_images(current: list[ListingImage], keep_ids: list[str]) -> list[ListingImage]:
    by_id = {str(image.id): image for image in current}
    return [by_id[image_id] for image_id in keep_ids if image_id in by_id]


def _category_rows(categories: list[Category]) -> list[dict[str, Any]]:
    """Depth-first, so a sub-category sits right under its parent."""
    children: dict[UUID | None, list[Category]] = {}
    known = {category.id for category in categories}
    for category in categories:
        parent = category.parent_id if category.parent_id in known else None
        children.setdefault(parent, []).append(category)

    rows: list[dict[str, Any]] = []

    def walk(parent: UUID | None, depth: int) -> None:
        for category in children.get(parent, []):
            rows.append({"category": category, "depth": depth})
            walk(category.id, depth + 1)

    walk(None, 0)
    return rows


class MarketplaceAdminController:

    __slots__ = ()

    # =========================================================
    # OVERVIEW
    # =========================================================

    @staticmethod
    async def overview_page(request: Request) -> Response:
        user = _seller(request)
        overview, low_stock = await GetHandler.marketplace_catalog_handler(request).overview(user)
        latest_orders, _ = await GetHandler.marketplace_order_handler(request).list_orders(user, None, None, 0, _LATEST_ORDERS)
        return _page(request, "overview.html", "overview", {
            "overview": overview, "low_stock": low_stock, "latest_orders": latest_orders,
        })

    # =========================================================
    # PRODUCTS
    # =========================================================

    @staticmethod
    async def products_page(request: Request, search: str = "", status: str = "", page: int = 1) -> Response:
        user = _seller(request)
        page = max(page, 1)
        handler = GetHandler.marketplace_catalog_handler(request)
        items, total = await handler.list_products(
            user, search or None, _parse_choice(ProductStatus, status), (page - 1) * _PAGE_SIZE, _PAGE_SIZE
        )
        categories = {category.id: category.name for category in await handler.list_categories(user)}
        return _page(request, "products.html", "products", {
            "items": items, "categories": categories, "search": search, "status": status,
            "statuses": list(ProductStatus), **_pagination(total, page),
        })

    @staticmethod
    async def _product_form(
        request: Request,
        values: dict[str, Any],
        images: list[ListingImage],
        product_id: UUID | None,
        errors: dict[str, str] | None = None,
        status_code: int = 200,
    ) -> Response:
        user = _seller(request)
        categories = await GetHandler.marketplace_catalog_handler(request).list_categories(user)
        return _page(request, "product_form.html", "products", {
            "form": values, "images": images, "product_id": product_id, "errors": errors or {},
            "category_rows": _category_rows(categories), "statuses": list(ProductStatus),
            "max_images": MAX_LISTING_IMAGES,
        }, status_code)

    @staticmethod
    async def product_new_page(request: Request) -> Response:
        return await MarketplaceAdminController._product_form(
            request, {"status": ProductStatus.DRAFT.value, "variants": [], "specifications": []}, [], None
        )

    @staticmethod
    async def product_edit_page(request: Request, product_id: UUID) -> Response:
        user = _seller(request)
        try:
            product = await GetHandler.marketplace_catalog_handler(request).get_product(user, product_id)
        except ProductNotFoundException:
            raise _not_found() from None
        return await MarketplaceAdminController._product_form(
            request, _product_values(product), product.images, product.id
        )

    @staticmethod
    async def _save_product(request: Request, product_id: UUID | None) -> Response:
        user = _seller(request)
        handler = GetHandler.marketplace_catalog_handler(request)
        form = await request.form()
        data = _product_data(form)
        new_images = _uploads(form, "new_images")

        current: list[ListingImage] = []
        if product_id is not None:
            try:
                current = (await handler.get_product(user, product_id)).images
            except ProductNotFoundException:
                raise _not_found() from None

        parsed, errors = parse_form(ProductForm, data)
        if parsed is not None:
            try:
                await handler.save_product(SaveProductCommand(
                    owner=user,
                    id=product_id,
                    variants=[VariantInput(**variant.model_dump()) for variant in parsed.variants],
                    new_images=new_images,
                    **parsed.model_dump(exclude={"variants"}),
                ))
                return _done("/products", "saved" if product_id else "created")
            except ListingValidationException as exc:
                errors = exc.errors

        if new_images:
            errors.setdefault("images", "Please choose your new images again.")
        return await MarketplaceAdminController._product_form(
            request, data, _kept_images(current, data["keep_image_ids"]), product_id, errors, 422
        )

    @staticmethod
    async def product_create(request: Request) -> Response:
        return await MarketplaceAdminController._save_product(request, None)

    @staticmethod
    async def product_update(request: Request, product_id: UUID) -> Response:
        return await MarketplaceAdminController._save_product(request, product_id)

    @staticmethod
    async def product_delete(request: Request, product_id: UUID) -> Response:
        user = _seller(request)
        try:
            await GetHandler.marketplace_catalog_handler(request).delete_product(user, product_id)
        except ProductNotFoundException:
            raise _not_found() from None
        return _done("/products", "deleted")

    # =========================================================
    # ANIMALS
    # =========================================================

    @staticmethod
    async def animals_page(request: Request, search: str = "", status: str = "", page: int = 1) -> Response:
        user = _seller(request)
        page = max(page, 1)
        handler = GetHandler.marketplace_catalog_handler(request)
        items, total = await handler.list_animals(
            user, search or None, _parse_choice(AnimalStatus, status), (page - 1) * _PAGE_SIZE, _PAGE_SIZE
        )
        types = {item.id: item.name for item in await handler.list_animal_types(user)}
        breeds = {item.id: item.name for item in await handler.list_animal_breeds(user)}
        return _page(request, "animals.html", "animals", {
            "items": items, "types": types, "breeds": breeds, "search": search, "status": status,
            "statuses": list(AnimalStatus), **_pagination(total, page),
        })

    @staticmethod
    async def _animal_form(
        request: Request,
        values: dict[str, Any],
        images: list[ListingImage],
        animal_id: UUID | None,
        errors: dict[str, str] | None = None,
        status_code: int = 200,
    ) -> Response:
        user = _seller(request)
        handler = GetHandler.marketplace_catalog_handler(request)
        return _page(request, "animal_form.html", "animals", {
            "form": values, "images": images, "animal_id": animal_id, "errors": errors or {},
            "animal_types": await handler.list_animal_types(user),
            "animal_breeds": await handler.list_animal_breeds(user),
            "statuses": list(AnimalStatus), "genders": list(AnimalGender),
            "pregnancy_statuses": list(PregnancyStatus), "max_images": MAX_LISTING_IMAGES,
        }, status_code)

    @staticmethod
    async def animal_new_page(request: Request) -> Response:
        return await MarketplaceAdminController._animal_form(
            request,
            {
                "status": AnimalStatus.DRAFT.value,
                "gender": AnimalGender.FEMALE.value,
                "pregnancy_status": PregnancyStatus.UNKNOWN.value,
            },
            [],
            None,
        )

    @staticmethod
    async def animal_edit_page(request: Request, animal_id: UUID) -> Response:
        user = _seller(request)
        try:
            animal = await GetHandler.marketplace_catalog_handler(request).get_animal(user, animal_id)
        except AnimalNotFoundException:
            raise _not_found() from None
        return await MarketplaceAdminController._animal_form(request, _animal_values(animal), animal.images, animal.id)

    @staticmethod
    async def _save_animal(request: Request, animal_id: UUID | None) -> Response:
        user = _seller(request)
        handler = GetHandler.marketplace_catalog_handler(request)
        form = await request.form()
        data = _animal_data(form)
        new_images = _uploads(form, "new_images")

        current: list[ListingImage] = []
        if animal_id is not None:
            try:
                current = (await handler.get_animal(user, animal_id)).images
            except AnimalNotFoundException:
                raise _not_found() from None

        parsed, errors = parse_form(AnimalForm, data)
        if parsed is not None:
            try:
                await handler.save_animal(SaveAnimalCommand(
                    owner=user, id=animal_id, new_images=new_images, **parsed.model_dump()
                ))
                return _done("/animals", "saved" if animal_id else "created")
            except ListingValidationException as exc:
                errors = exc.errors

        if new_images:
            errors.setdefault("images", "Please choose your new images again.")
        return await MarketplaceAdminController._animal_form(
            request, data, _kept_images(current, data["keep_image_ids"]), animal_id, errors, 422
        )

    @staticmethod
    async def animal_create(request: Request) -> Response:
        return await MarketplaceAdminController._save_animal(request, None)

    @staticmethod
    async def animal_update(request: Request, animal_id: UUID) -> Response:
        return await MarketplaceAdminController._save_animal(request, animal_id)

    @staticmethod
    async def animal_delete(request: Request, animal_id: UUID) -> Response:
        user = _seller(request)
        try:
            await GetHandler.marketplace_catalog_handler(request).delete_animal(user, animal_id)
        except AnimalNotFoundException:
            raise _not_found() from None
        return _done("/animals", "deleted")

    # =========================================================
    # ENQUIRIES
    # =========================================================

    @staticmethod
    async def enquiries_page(request: Request, search: str = "", status: str = "", page: int = 1) -> Response:
        user = _seller(request)
        page = max(page, 1)
        items, total = await GetHandler.marketplace_catalog_handler(request).list_enquiries(
            user, search or None, _parse_choice(EnquiryStatus, status), (page - 1) * _PAGE_SIZE, _PAGE_SIZE
        )
        return _page(request, "enquiries.html", "enquiries", {
            "items": items, "search": search, "status": status, "statuses": list(EnquiryStatus),
            **_pagination(total, page),
        })

    @staticmethod
    async def enquiry_update(request: Request, enquiry_id: UUID) -> Response:
        user = _seller(request)
        form = await request.form()
        parsed, _ = parse_form(EnquiryUpdateForm, _text_fields(form, ("status", "admin_notes")))
        if parsed is None:
            return RedirectResponse(url=f"{_BASE}/enquiries", status_code=303)
        try:
            await GetHandler.marketplace_catalog_handler(request).update_enquiry(
                UpdateEnquiryCommand(owner=user, id=enquiry_id, **parsed.model_dump())
            )
        except EnquiryNotFoundException:
            raise _not_found() from None
        return _done("/enquiries", "saved")

    # =========================================================
    # CATEGORIES
    # =========================================================

    @staticmethod
    async def categories_page(request: Request, edit: UUID | None = None) -> Response:
        return await MarketplaceAdminController._categories_view(request, edit)

    @staticmethod
    async def _categories_view(
        request: Request,
        edit: UUID | None = None,
        values: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        page_error: str | None = None,
        status_code: int = 200,
    ) -> Response:
        user = _super_admin(request)
        categories = await GetHandler.marketplace_catalog_handler(request).list_categories(user)
        editing = next((category for category in categories if category.id == edit), None)
        if edit is not None and editing is None:
            raise _not_found()
        if values is None:
            values = asdict(editing) if editing else {"is_active": True, "sort_order": 0}
        return _page(request, "categories.html", "categories", {
            "rows": _category_rows(categories), "form": values, "editing": editing,
            "errors": errors or {}, "page_error": page_error,
        }, status_code)

    @staticmethod
    async def category_save(request: Request) -> Response:
        user = _super_admin(request)
        form = await request.form()
        category_id = _parse_choice(UUID, str(form.get("id", "")))
        data = _text_fields(form, ("name", "parent_id", "description", "sort_order", "is_active", "remove_image"))
        parsed, errors = parse_form(CategoryForm, data)
        if parsed is not None:
            try:
                await GetHandler.marketplace_catalog_handler(request).save_category(SaveCategoryCommand(
                    owner=user, id=category_id, new_image=_upload(form, "image"), **parsed.model_dump()
                ))
                return _done("/categories", "saved" if category_id else "created")
            except ListingValidationException as exc:
                errors = exc.errors
            except CategoryNotFoundException:
                raise _not_found() from None
        return await MarketplaceAdminController._categories_view(
            request, edit=category_id, values=data, errors=errors, status_code=422
        )

    @staticmethod
    async def category_delete(request: Request, category_id: UUID) -> Response:
        user = _super_admin(request)
        try:
            await GetHandler.marketplace_catalog_handler(request).delete_category(user, category_id)
        except CategoryNotFoundException:
            raise _not_found() from None
        except MasterInUseException as exc:
            return await MarketplaceAdminController._categories_view(request, page_error=exc.message, status_code=409)
        return _done("/categories", "deleted")

    # =========================================================
    # ANIMAL TYPES & BREEDS
    # =========================================================

    @staticmethod
    async def animal_types_page(request: Request, edit: UUID | None = None) -> Response:
        return await MarketplaceAdminController._animal_types_view(request, edit)

    @staticmethod
    async def _animal_types_view(
        request: Request,
        edit: UUID | None = None,
        values: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        breed_errors: dict[str, str] | None = None,
        page_error: str | None = None,
        status_code: int = 200,
    ) -> Response:
        user = _super_admin(request)
        handler = GetHandler.marketplace_catalog_handler(request)
        animal_types = await handler.list_animal_types(user)
        breeds = await handler.list_animal_breeds(user)
        editing = next((item for item in animal_types if item.id == edit), None)
        if edit is not None and editing is None:
            raise _not_found()
        if values is None:
            values = asdict(editing) if editing else {"is_active": True, "sort_order": 0}
        return _page(request, "animal_types.html", "animal_types", {
            "animal_types": animal_types,
            "breeds_by_type": {
                item.id: [breed for breed in breeds if breed.animal_type_id == item.id] for item in animal_types
            },
            "form": values, "editing": editing, "errors": errors or {},
            "breed_errors": breed_errors or {}, "page_error": page_error,
        }, status_code)

    @staticmethod
    async def animal_type_save(request: Request) -> Response:
        user = _super_admin(request)
        form = await request.form()
        type_id = _parse_choice(UUID, str(form.get("id", "")))
        data = _text_fields(form, ("name", "sort_order", "is_active", "remove_image"))
        parsed, errors = parse_form(AnimalTypeForm, data)
        if parsed is not None:
            try:
                await GetHandler.marketplace_catalog_handler(request).save_animal_type(SaveAnimalTypeCommand(
                    owner=user, id=type_id, new_image=_upload(form, "image"), **parsed.model_dump()
                ))
                return _done("/animal-types", "saved" if type_id else "created")
            except ListingValidationException as exc:
                errors = exc.errors
            except AnimalTypeNotFoundException:
                raise _not_found() from None
        return await MarketplaceAdminController._animal_types_view(
            request, edit=type_id, values=data, errors=errors, status_code=422
        )

    @staticmethod
    async def animal_type_delete(request: Request, animal_type_id: UUID) -> Response:
        user = _super_admin(request)
        try:
            await GetHandler.marketplace_catalog_handler(request).delete_animal_type(user, animal_type_id)
        except AnimalTypeNotFoundException:
            raise _not_found() from None
        except MasterInUseException as exc:
            return await MarketplaceAdminController._animal_types_view(request, page_error=exc.message, status_code=409)
        return _done("/animal-types", "deleted")

    @staticmethod
    async def animal_breed_save(request: Request) -> Response:
        user = _super_admin(request)
        form = await request.form()
        data = _text_fields(form, ("animal_type_id", "name", "sort_order", "is_active"))
        parsed, errors = parse_form(AnimalBreedForm, data)
        if parsed is not None:
            try:
                await GetHandler.marketplace_catalog_handler(request).save_animal_breed(
                    SaveAnimalBreedCommand(owner=user, **parsed.model_dump())
                )
                return _done("/animal-types", "created")
            except ListingValidationException as exc:
                errors = exc.errors
            except AnimalTypeNotFoundException:
                raise _not_found() from None
        return await MarketplaceAdminController._animal_types_view(
            request, breed_errors={data.get("animal_type_id", ""): errors.get("name", "Check this breed.")}, status_code=422
        )

    @staticmethod
    async def animal_breed_delete(request: Request, breed_id: UUID) -> Response:
        user = _super_admin(request)
        try:
            await GetHandler.marketplace_catalog_handler(request).delete_animal_breed(user, breed_id)
        except AnimalBreedNotFoundException:
            raise _not_found() from None
        except MasterInUseException as exc:
            return await MarketplaceAdminController._animal_types_view(request, page_error=exc.message, status_code=409)
        return _done("/animal-types", "deleted")
