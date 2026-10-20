"""
Permission checks backed by an MCC / VLCC's settings record.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.vlcc.infrastructure.models import VlccModel

_ALWAYS_ALLOWED = (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN)


async def can_create_masters(session: AsyncSession, owner: CurrentUser | None) -> bool:
    """
    Item & Unit masters: Super Admin / Admin / Sub Admin always; an MCC or
    VLCC only when its settings have the "Item & Unit Masters" permission
    (`master_enabled`); nobody else.
    """
    if owner is None:
        return False
    role = owner.role_type
    if role in _ALWAYS_ALLOWED:
        return True

    unit = {Role.MCC: MccModel, Role.VLCC: VlccModel}.get(role)
    if unit is None:
        return False
    enabled = await session.scalar(
        select(SettingsModel.master_enabled)
        .join(unit, unit.settings_id == SettingsModel.id)
        .where(unit.user_id == owner.id)
    )
    return bool(enabled)


async def can_edit_rate_charts(session: AsyncSession, owner: CurrentUser | None) -> bool:
    """
    Create / modify rate charts: Super Admin / Admin / Sub Admin always; an MCC
    or VLCC only when its settings have the rate chart permission
    (`rate_chart_edit_enabled`). Everyone may still view the charts they can see.
    """
    if owner is None:
        return False
    role = owner.role_type
    if role in _ALWAYS_ALLOWED:
        return True

    unit = {Role.MCC: MccModel, Role.VLCC: VlccModel}.get(role)
    if unit is None:
        return False
    enabled = await session.scalar(
        select(SettingsModel.rate_chart_edit_enabled)
        .join(unit, unit.settings_id == SettingsModel.id)
        .where(unit.user_id == owner.id)
    )
    return bool(enabled)


DEFAULT_MAX_RATE_CHARTS = 5


async def rate_chart_limit(session: AsyncSession, owner: CurrentUser | None) -> int | None:
    """
    How many rate charts the owner may create: an MCC / VLCC is capped by its
    settings' `max_rate_chart_count` (system default when it has no settings);
    management roles have no cap (None).
    """
    if owner is None:
        return None
    unit = {Role.MCC: MccModel, Role.VLCC: VlccModel}.get(owner.role_type)
    if unit is None:
        return None
    limit = await session.scalar(
        select(SettingsModel.max_rate_chart_count)
        .join(unit, unit.settings_id == SettingsModel.id)
        .where(unit.user_id == owner.id)
    )
    return DEFAULT_MAX_RATE_CHARTS if limit is None else int(limit)
