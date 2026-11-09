"""
Storefront content and store settings use cases. These affect the whole store, so only
the Super Admin may use them, even after other roles can sell (DECISION-016).

Images are decoded before the first write (DECISION-010).

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.application.command import (
    SaveBannerCommand,
    SaveHomeSectionCommand,
    SaveSettingsCommand,
    SaveTrendingTagCommand,
)
from app.modules.marketplace.domain.entities import ListingViewer
from app.modules.marketplace.domain.enums import HomeSectionType
from app.modules.marketplace.domain.exceptions import (
    BannerNotFoundException,
    HomeSectionNotFoundException,
    ListingValidationException,
    SellingNotAllowedException,
    TrendingTagNotFoundException,
)
from app.modules.marketplace.domain.merchandising import (
    POLICY_KEYS,
    Banner,
    HomeSection,
    StoreSettings,
    TrendingTag,
)
from app.modules.marketplace.domain.irepository import IMerchandisingRepository
from app.modules.media.application.services import MediaService, MediaUrlService
from app.modules.media.domain.enums import MediaCategory

DEFAULT_STORE_NAME = "Vitco Marketplace"


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


class MarketplaceMerchandisingHandler:

    __slots__ = ("_database", "_repository", "_media")

    def __init__(
        self,
        database: DatabaseManager,
        repository: IMerchandisingRepository,
        media_service: MediaService,
    ) -> None:
        self._database = database
        self._repository = repository
        self._media = media_service

    @staticmethod
    def _super_admin(owner: ListingViewer | None) -> ListingViewer:
        if owner is None or owner.role_type != Role.SUPER_ADMIN:
            raise SellingNotAllowedException("Only the Super Admin can change the store's content and settings.")
        return owner

    async def _prepare(self, file: Any | None, name: str, errors: dict[str, str]) -> Any | None:
        if file is None:
            return None
        try:
            return await self._media.prepare_listing_image(file)
        except ValueError as error:
            errors[name] = str(error)
            return None

    async def _store(self, prepared: Any, owner: ListingViewer, name: str) -> str:
        media = await self._media.store_listing_image(prepared, MediaCategory.BANNER, owner.id, name)
        return MediaUrlService.build(media.storage_key)

    # =========================================================
    # BANNERS
    # =========================================================

    async def list_banners(self, owner: ListingViewer | None) -> tuple[list[Banner], datetime]:
        self._super_admin(owner)
        return await self._repository.list_banners(), now_naive_ist()

    async def save_banner(self, command: SaveBannerCommand) -> Banner:
        owner = self._super_admin(command.owner)
        errors: dict[str, str] = {}
        image = await self._prepare(command.new_image, "image", errors)
        mobile = await self._prepare(command.new_mobile_image, "mobile_image", errors)

        async with self._database.transaction():
            current = None
            if command.id is not None:
                current = await self._repository.get_banner(command.id)
                if current is None:
                    raise BannerNotFoundException()
            if current is None and image is None and "image" not in errors:
                errors["image"] = "Choose a banner image."

            banner = Banner(
                id=current.id if current else uuid4(),
                title=command.title.strip(),
                subtitle=_clean(command.subtitle),
                cta_label=_clean(command.cta_label),
                cta_url=_clean(command.cta_url),
                image_url=current.image_url if current else "",
                mobile_image_url=current.mobile_image_url if current else None,
                placement=command.placement,
                starts_at=command.starts_at,
                ends_at=command.ends_at,
                sort_order=command.sort_order,
                is_active=command.is_active,
                created_by=current.created_by if current else owner.id,
            )
            errors = {**banner.problems(), **errors}
            if errors:
                raise ListingValidationException(errors)

            if image is not None:
                await self._media.delete_image_by_url(banner.image_url)
                banner.image_url = await self._store(image, owner, banner.title)
            if mobile is not None or command.remove_mobile_image:
                await self._media.delete_image_by_url(banner.mobile_image_url)
                banner.mobile_image_url = await self._store(mobile, owner, banner.title) if mobile else None
            await self._repository.save_banner(banner)
        return banner

    async def delete_banner(self, owner: ListingViewer | None, banner_id: UUID) -> None:
        self._super_admin(owner)
        async with self._database.transaction():
            banner = await self._repository.get_banner(banner_id)
            if banner is None:
                raise BannerNotFoundException()
            await self._repository.delete_banner(banner_id)
            await self._media.delete_image_by_url(banner.image_url)
            await self._media.delete_image_by_url(banner.mobile_image_url)

    # =========================================================
    # HOME SECTIONS
    # =========================================================

    async def list_home_sections(self, owner: ListingViewer | None) -> list[HomeSection]:
        self._super_admin(owner)
        return await self._repository.list_home_sections()

    async def save_home_section(self, command: SaveHomeSectionCommand) -> HomeSection:
        self._super_admin(command.owner)
        async with self._database.transaction():
            sections = await self._repository.list_home_sections()
            current = None
            if command.id is not None:
                current = next((section for section in sections if section.id == command.id), None)
                if current is None:
                    raise HomeSectionNotFoundException()
            section = HomeSection(
                id=current.id if current else uuid4(),
                section_type=current.section_type if current else HomeSectionType.CATEGORY_PRODUCTS,
                title=command.title.strip(),
                subtitle=_clean(command.subtitle),
                category_id=command.category_id,
                item_limit=command.item_limit,
                sort_order=current.sort_order if current else len(sections),
                is_visible=command.is_visible,
            )
            problems = section.problems()
            if problems:
                raise ListingValidationException(problems)
            await self._repository.save_home_section(section)
        return section

    async def move_home_section(self, owner: ListingViewer | None, section_id: UUID, direction: int) -> None:
        self._super_admin(owner)
        async with self._database.transaction():
            sections = await self._repository.list_home_sections()
            index = next((i for i, section in enumerate(sections) if section.id == section_id), None)
            if index is None:
                raise HomeSectionNotFoundException()
            target = index + (1 if direction > 0 else -1)
            if 0 <= target < len(sections):
                sections[index], sections[target] = sections[target], sections[index]
            for order, section in enumerate(sections):
                section.sort_order = order
                await self._repository.save_home_section(section)

    async def delete_home_section(self, owner: ListingViewer | None, section_id: UUID) -> None:
        self._super_admin(owner)
        async with self._database.transaction():
            section = await self._repository.get_home_section(section_id)
            if section is None:
                raise HomeSectionNotFoundException()
            if not section.can_delete:
                raise ListingValidationException({"section": "Built-in sections can be hidden but not deleted."})
            await self._repository.delete_home_section(section_id)

    # =========================================================
    # TRENDING TAGS
    # =========================================================

    async def list_trending_tags(self, owner: ListingViewer | None) -> list[TrendingTag]:
        self._super_admin(owner)
        return await self._repository.list_trending_tags()

    async def save_trending_tag(self, command: SaveTrendingTagCommand) -> TrendingTag:
        self._super_admin(command.owner)
        tag = TrendingTag(
            id=command.id or uuid4(),
            label=command.label.strip(),
            url=command.url.strip(),
            sort_order=command.sort_order,
            is_active=command.is_active,
        )
        problems = tag.problems()
        if problems:
            raise ListingValidationException(problems)
        async with self._database.transaction():
            if command.id is not None and await self._repository.get_trending_tag(command.id) is None:
                raise TrendingTagNotFoundException()
            await self._repository.save_trending_tag(tag)
        return tag

    async def delete_trending_tag(self, owner: ListingViewer | None, tag_id: UUID) -> None:
        self._super_admin(owner)
        async with self._database.transaction():
            if await self._repository.get_trending_tag(tag_id) is None:
                raise TrendingTagNotFoundException()
            await self._repository.delete_trending_tag(tag_id)

    # =========================================================
    # SETTINGS
    # =========================================================

    async def get_settings(self, owner: ListingViewer | None) -> StoreSettings:
        self._super_admin(owner)
        return await self._repository.get_settings() or StoreSettings(store_name=DEFAULT_STORE_NAME)

    async def save_settings(self, command: SaveSettingsCommand) -> StoreSettings:
        owner = self._super_admin(command.owner)
        errors: dict[str, str] = {}
        logo = await self._prepare(command.new_logo, "logo", errors)

        async with self._database.transaction():
            current = await self._repository.get_settings()
            settings = StoreSettings(
                store_name=command.store_name.strip(),
                tagline=_clean(command.tagline),
                logo_url=current.logo_url if current else None,
                support_phone=_clean(command.support_phone),
                whatsapp_number=_clean(command.whatsapp_number),
                support_email=_clean(command.support_email),
                address=_clean(command.address),
                delivery_charge=command.delivery_charge,
                free_delivery_above=command.free_delivery_above,
                min_order_amount=command.min_order_amount,
                cod_enabled=command.cod_enabled,
                serviceable_pincodes=list(dict.fromkeys(command.serviceable_pincodes)),
                is_store_open=command.is_store_open,
                closed_message=_clean(command.closed_message),
                policies={key: value.strip() for key, value in command.policies.items() if key in POLICY_KEYS and value.strip()},
            )
            errors = {**settings.problems(), **errors}
            if errors:
                raise ListingValidationException(errors)

            if logo is not None or command.remove_logo:
                await self._media.delete_image_by_url(settings.logo_url)
                settings.logo_url = await self._store(logo, owner, "Store logo") if logo else None
            await self._repository.save_settings(settings, owner.id)
        return settings
