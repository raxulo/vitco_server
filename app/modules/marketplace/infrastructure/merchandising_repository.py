"""
Storefront content and store settings repository.

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.marketplace.domain.enums import BannerPlacement
from app.modules.marketplace.domain.irepository import IMerchandisingRepository
from app.modules.marketplace.domain.merchandising import Banner, HomeSection, StoreSettings, TrendingTag
from app.modules.marketplace.infrastructure.models import (
    MarketplaceBannerModel,
    MarketplaceHomeSectionModel,
    MarketplaceSettingsModel,
    MarketplaceTrendingTagModel,
)

_BANNER_FIELDS = (
    "title", "subtitle", "cta_label", "cta_url", "image_url", "mobile_image_url", "placement",
    "starts_at", "ends_at", "sort_order", "is_active",
)
_SECTION_FIELDS = ("section_type", "title", "subtitle", "category_id", "item_limit", "sort_order", "is_visible")
_TAG_FIELDS = ("label", "url", "sort_order", "is_active")
_SETTINGS_FIELDS = (
    "store_name", "tagline", "logo_url", "support_phone", "whatsapp_number", "support_email", "address",
    "delivery_charge", "free_delivery_above", "min_order_amount", "cod_enabled", "is_store_open", "closed_message",
)


def _values(source, fields: tuple[str, ...]) -> dict:
    return {name: getattr(source, name) for name in fields}


def _copy(source, target, fields: tuple[str, ...]) -> None:
    for name in fields:
        setattr(target, name, getattr(source, name))


def _banner(model: MarketplaceBannerModel) -> Banner:
    return Banner(id=model.id, created_by=model.created_by, **_values(model, _BANNER_FIELDS))


def _section(model: MarketplaceHomeSectionModel) -> HomeSection:
    return HomeSection(id=model.id, **_values(model, _SECTION_FIELDS))


def _tag(model: MarketplaceTrendingTagModel) -> TrendingTag:
    return TrendingTag(id=model.id, **_values(model, _TAG_FIELDS))


class MerchandisingRepository(IMerchandisingRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # BANNERS
    # =========================================================

    async def save_banner(self, banner: Banner) -> None:
        model = await self._session.get(MarketplaceBannerModel, banner.id)
        if model is None:
            self._session.add(
                MarketplaceBannerModel(id=banner.id, created_by=banner.created_by, **_values(banner, _BANNER_FIELDS))
            )
        else:
            _copy(banner, model, _BANNER_FIELDS)

    async def get_banner(self, banner_id: UUID) -> Banner | None:
        model = await self._session.get(MarketplaceBannerModel, banner_id)
        return None if model is None else _banner(model)

    async def list_banners(self) -> list[Banner]:
        stmt = select(MarketplaceBannerModel).order_by(
            MarketplaceBannerModel.placement, MarketplaceBannerModel.sort_order, MarketplaceBannerModel.title
        )
        return [_banner(model) for model in await self._session.scalars(stmt)]

    async def live_banners(self, placement: BannerPlacement, now: datetime) -> list[Banner]:
        stmt = (
            select(MarketplaceBannerModel)
            .where(
                MarketplaceBannerModel.placement == placement,
                MarketplaceBannerModel.is_active.is_(True),
                or_(MarketplaceBannerModel.starts_at.is_(None), MarketplaceBannerModel.starts_at <= now),
                or_(MarketplaceBannerModel.ends_at.is_(None), MarketplaceBannerModel.ends_at > now),
            )
            .order_by(MarketplaceBannerModel.sort_order, MarketplaceBannerModel.title)
        )
        return [_banner(model) for model in await self._session.scalars(stmt)]

    async def delete_banner(self, banner_id: UUID) -> None:
        await self._session.execute(delete(MarketplaceBannerModel).where(MarketplaceBannerModel.id == banner_id))

    # =========================================================
    # HOME SECTIONS
    # =========================================================

    async def save_home_section(self, section: HomeSection) -> None:
        model = await self._session.get(MarketplaceHomeSectionModel, section.id)
        if model is None:
            self._session.add(MarketplaceHomeSectionModel(id=section.id, **_values(section, _SECTION_FIELDS)))
        else:
            _copy(section, model, _SECTION_FIELDS)

    async def get_home_section(self, section_id: UUID) -> HomeSection | None:
        model = await self._session.get(MarketplaceHomeSectionModel, section_id)
        return None if model is None else _section(model)

    async def list_home_sections(self, visible_only: bool = False) -> list[HomeSection]:
        stmt = select(MarketplaceHomeSectionModel).order_by(
            MarketplaceHomeSectionModel.sort_order, MarketplaceHomeSectionModel.title
        )
        if visible_only:
            stmt = stmt.where(MarketplaceHomeSectionModel.is_visible.is_(True))
        return [_section(model) for model in await self._session.scalars(stmt)]

    async def delete_home_section(self, section_id: UUID) -> None:
        await self._session.execute(
            delete(MarketplaceHomeSectionModel).where(MarketplaceHomeSectionModel.id == section_id)
        )

    # =========================================================
    # TRENDING TAGS
    # =========================================================

    async def save_trending_tag(self, tag: TrendingTag) -> None:
        model = await self._session.get(MarketplaceTrendingTagModel, tag.id)
        if model is None:
            self._session.add(MarketplaceTrendingTagModel(id=tag.id, **_values(tag, _TAG_FIELDS)))
        else:
            _copy(tag, model, _TAG_FIELDS)

    async def get_trending_tag(self, tag_id: UUID) -> TrendingTag | None:
        model = await self._session.get(MarketplaceTrendingTagModel, tag_id)
        return None if model is None else _tag(model)

    async def list_trending_tags(self, active_only: bool = False) -> list[TrendingTag]:
        stmt = select(MarketplaceTrendingTagModel).order_by(
            MarketplaceTrendingTagModel.sort_order, MarketplaceTrendingTagModel.label
        )
        if active_only:
            stmt = stmt.where(MarketplaceTrendingTagModel.is_active.is_(True))
        return [_tag(model) for model in await self._session.scalars(stmt)]

    async def delete_trending_tag(self, tag_id: UUID) -> None:
        await self._session.execute(
            delete(MarketplaceTrendingTagModel).where(MarketplaceTrendingTagModel.id == tag_id)
        )

    # =========================================================
    # SETTINGS
    # =========================================================

    async def get_settings(self) -> StoreSettings | None:
        model = await self._session.scalar(select(MarketplaceSettingsModel))
        if model is None:
            return None
        return StoreSettings(
            serviceable_pincodes=list(model.serviceable_pincodes or []),
            policies=dict(model.policies or {}),
            **_values(model, _SETTINGS_FIELDS),
        )

    async def save_settings(self, settings: StoreSettings, updated_by: UUID) -> None:
        model = await self._session.scalar(select(MarketplaceSettingsModel))
        if model is None:
            model = MarketplaceSettingsModel(created_by=updated_by)
            self._session.add(model)
        _copy(settings, model, _SETTINGS_FIELDS)
        model.serviceable_pincodes = settings.serviceable_pincodes
        model.policies = settings.policies
        model.updated_by = updated_by
