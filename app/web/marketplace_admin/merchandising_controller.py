"""
Control Center: banners, home page content and store settings. Super Admin only.

Python 3.13+
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any
from uuid import UUID

from fastapi import Request
from starlette.responses import Response

from app.core.clock import to_naive_ist
from app.modules.dependencies import GetHandler
from app.modules.marketplace.application.command import (
    SaveBannerCommand,
    SaveHomeSectionCommand,
    SaveSettingsCommand,
    SaveTrendingTagCommand,
)
from app.modules.marketplace.domain.enums import BannerPlacement, BannerState
from app.modules.marketplace.domain.exceptions import (
    BannerNotFoundException,
    HomeSectionNotFoundException,
    ListingValidationException,
    TrendingTagNotFoundException,
)
from app.modules.marketplace.domain.merchandising import POLICY_KEYS, Banner
from app.modules.marketplace.presentation.requests import (
    BannerForm,
    HomeSectionForm,
    SettingsForm,
    TrendingTagForm,
    parse_form,
)
from app.web.marketplace_admin.controller import (
    _category_rows,
    _done,
    _not_found,
    _page,
    _parse_choice,
    _super_admin,
    _text_fields,
    _upload,
)

_BANNER_FIELDS = (
    "title", "subtitle", "cta_label", "cta_url", "placement", "starts_at", "ends_at", "sort_order", "is_active",
    "remove_mobile_image",
)
_SECTION_FIELDS = ("title", "subtitle", "category_id", "item_limit", "is_visible")
_TAG_FIELDS = ("label", "url", "sort_order", "is_active")
_SETTINGS_FIELDS = (
    "store_name", "tagline", "support_phone", "whatsapp_number", "support_email", "address", "delivery_charge",
    "free_delivery_above", "min_order_amount", "cod_enabled", "is_store_open", "closed_message", "remove_logo",
)
_STATE_PILLS = {
    BannerState.LIVE: "mk-pill-published",
    BannerState.SCHEDULED: "mk-pill-reserved",
    BannerState.EXPIRED: "mk-pill-off",
    BannerState.OFF: "mk-pill-off",
}


def _banner_values(banner: Banner) -> dict[str, Any]:
    values = asdict(banner)
    values["placement"] = banner.placement.value
    for name in ("starts_at", "ends_at"):
        value = getattr(banner, name)
        values[name] = value.strftime("%Y-%m-%dT%H:%M") if value else ""
    return values


class MerchandisingController:

    __slots__ = ()

    # =========================================================
    # BANNERS
    # =========================================================

    @staticmethod
    async def banners_page(request: Request, edit: UUID | None = None) -> Response:
        return await MerchandisingController._banners_view(request, edit)

    @staticmethod
    async def _banners_view(
        request: Request,
        edit: UUID | None = None,
        values: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        status_code: int = 200,
    ) -> Response:
        user = _super_admin(request)
        banners, now = await GetHandler.marketplace_merchandising_handler(request).list_banners(user)
        editing = next((banner for banner in banners if banner.id == edit), None)
        if edit is not None and editing is None:
            raise _not_found()
        if values is None:
            values = _banner_values(editing) if editing else {
                "is_active": True, "sort_order": 0, "placement": BannerPlacement.HOME_HERO.value,
            }
        elif editing:
            values = {"image_url": editing.image_url, "mobile_image_url": editing.mobile_image_url, **values}
        rows = [
            {"banner": banner, "state": banner.state(now), "pill": _STATE_PILLS[banner.state(now)]}
            for banner in banners
        ]
        return _page(request, "banners.html", "banners", {
            "rows": rows, "form": values, "editing": editing, "errors": errors or {},
            "placements": list(BannerPlacement),
        }, status_code)

    @staticmethod
    async def banner_save(request: Request) -> Response:
        user = _super_admin(request)
        form = await request.form()
        banner_id = _parse_choice(UUID, str(form.get("id", "")))
        data = _text_fields(form, _BANNER_FIELDS)
        parsed, errors = parse_form(BannerForm, data)
        if parsed is not None:
            fields = parsed.model_dump()
            for name in ("starts_at", "ends_at"):
                fields[name] = to_naive_ist(fields[name]) if fields[name] else None
            try:
                await GetHandler.marketplace_merchandising_handler(request).save_banner(SaveBannerCommand(
                    owner=user, id=banner_id, new_image=_upload(form, "image"),
                    new_mobile_image=_upload(form, "mobile_image"), **fields,
                ))
                return _done("/banners", "saved" if banner_id else "created")
            except ListingValidationException as exc:
                errors = exc.errors
            except BannerNotFoundException:
                raise _not_found() from None
        return await MerchandisingController._banners_view(
            request, edit=banner_id, values=data, errors=errors, status_code=422
        )

    @staticmethod
    async def banner_delete(request: Request, banner_id: UUID) -> Response:
        user = _super_admin(request)
        try:
            await GetHandler.marketplace_merchandising_handler(request).delete_banner(user, banner_id)
        except BannerNotFoundException:
            raise _not_found() from None
        return _done("/banners", "deleted")

    # =========================================================
    # HOME PAGE
    # =========================================================

    @staticmethod
    async def home_page(request: Request, edit: UUID | None = None, edit_tag: UUID | None = None) -> Response:
        return await MerchandisingController._home_view(request, edit, edit_tag)

    @staticmethod
    async def _home_view(
        request: Request,
        edit: UUID | None = None,
        edit_tag: UUID | None = None,
        section_values: dict[str, Any] | None = None,
        section_errors: dict[str, str] | None = None,
        tag_values: dict[str, Any] | None = None,
        tag_errors: dict[str, str] | None = None,
        page_error: str | None = None,
        status_code: int = 200,
    ) -> Response:
        user = _super_admin(request)
        handler = GetHandler.marketplace_merchandising_handler(request)
        sections = await handler.list_home_sections(user)
        tags = await handler.list_trending_tags(user)
        categories = await GetHandler.marketplace_catalog_handler(request).list_categories(user)

        editing = next((section for section in sections if section.id == edit), None)
        editing_tag = next((tag for tag in tags if tag.id == edit_tag), None)
        if (edit is not None and editing is None) or (edit_tag is not None and editing_tag is None):
            raise _not_found()
        if section_values is None:
            section_values = asdict(editing) if editing else {"item_limit": 8, "is_visible": True}
        if tag_values is None:
            tag_values = asdict(editing_tag) if editing_tag else {"is_active": True, "sort_order": 0}

        return _page(request, "home_page.html", "home", {
            "sections": sections, "tags": tags, "category_rows": _category_rows(categories),
            "category_names": {category.id: category.name for category in categories},
            "editing": editing, "section_form": section_values, "section_errors": section_errors or {},
            "editing_tag": editing_tag, "tag_form": tag_values, "tag_errors": tag_errors or {},
            "page_error": page_error,
        }, status_code)

    @staticmethod
    async def section_save(request: Request) -> Response:
        user = _super_admin(request)
        form = await request.form()
        section_id = _parse_choice(UUID, str(form.get("id", "")))
        data = _text_fields(form, _SECTION_FIELDS)
        parsed, errors = parse_form(HomeSectionForm, data)
        if parsed is not None:
            try:
                await GetHandler.marketplace_merchandising_handler(request).save_home_section(
                    SaveHomeSectionCommand(owner=user, id=section_id, **parsed.model_dump())
                )
                return _done("/home", "saved" if section_id else "created")
            except ListingValidationException as exc:
                errors = exc.errors
            except HomeSectionNotFoundException:
                raise _not_found() from None
        return await MerchandisingController._home_view(
            request, edit=section_id, section_values=data, section_errors=errors, status_code=422
        )

    @staticmethod
    async def section_move(request: Request, section_id: UUID) -> Response:
        user = _super_admin(request)
        form = await request.form()
        direction = 1 if form.get("direction") == "down" else -1
        try:
            await GetHandler.marketplace_merchandising_handler(request).move_home_section(user, section_id, direction)
        except HomeSectionNotFoundException:
            raise _not_found() from None
        return _done("/home", "saved")

    @staticmethod
    async def section_delete(request: Request, section_id: UUID) -> Response:
        user = _super_admin(request)
        try:
            await GetHandler.marketplace_merchandising_handler(request).delete_home_section(user, section_id)
        except HomeSectionNotFoundException:
            raise _not_found() from None
        except ListingValidationException as exc:
            return await MerchandisingController._home_view(
                request, page_error=exc.errors.get("section"), status_code=409
            )
        return _done("/home", "deleted")

    @staticmethod
    async def tag_save(request: Request) -> Response:
        user = _super_admin(request)
        form = await request.form()
        tag_id = _parse_choice(UUID, str(form.get("id", "")))
        data = _text_fields(form, _TAG_FIELDS)
        parsed, errors = parse_form(TrendingTagForm, data)
        if parsed is not None:
            try:
                await GetHandler.marketplace_merchandising_handler(request).save_trending_tag(
                    SaveTrendingTagCommand(owner=user, id=tag_id, **parsed.model_dump())
                )
                return _done("/home", "saved" if tag_id else "created")
            except ListingValidationException as exc:
                errors = exc.errors
            except TrendingTagNotFoundException:
                raise _not_found() from None
        return await MerchandisingController._home_view(
            request, edit_tag=tag_id, tag_values=data, tag_errors=errors, status_code=422
        )

    @staticmethod
    async def tag_delete(request: Request, tag_id: UUID) -> Response:
        user = _super_admin(request)
        try:
            await GetHandler.marketplace_merchandising_handler(request).delete_trending_tag(user, tag_id)
        except TrendingTagNotFoundException:
            raise _not_found() from None
        return _done("/home", "deleted")

    # =========================================================
    # SETTINGS
    # =========================================================

    @staticmethod
    async def settings_page(request: Request) -> Response:
        user = _super_admin(request)
        settings = await GetHandler.marketplace_merchandising_handler(request).get_settings(user)
        values = asdict(settings)
        values["pincodes_text"] = ", ".join(settings.serviceable_pincodes)
        return _page(request, "settings.html", "settings", {"form": values, "errors": {}})

    @staticmethod
    async def settings_save(request: Request) -> Response:
        user = _super_admin(request)
        form = await request.form()
        handler = GetHandler.marketplace_merchandising_handler(request)
        pincodes_text = str(form.get("pincodes_text", ""))
        policies = {key: str(form.get(f"policy_{key}", "")) for key in POLICY_KEYS}
        data = {
            **_text_fields(form, _SETTINGS_FIELDS),
            "serviceable_pincodes": [code for code in re.split(r"[\s,]+", pincodes_text) if code],
            "policies": policies,
        }
        parsed, errors = parse_form(SettingsForm, data)
        if parsed is not None:
            try:
                await handler.save_settings(SaveSettingsCommand(
                    owner=user, new_logo=_upload(form, "logo"), **parsed.model_dump()
                ))
                return _done("/settings", "saved")
            except ListingValidationException as exc:
                errors = exc.errors
        current = await handler.get_settings(user)
        values = {**data, "pincodes_text": pincodes_text, "logo_url": current.logo_url}
        return _page(request, "settings.html", "settings", {"form": values, "errors": errors}, 422)
