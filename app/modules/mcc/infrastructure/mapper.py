from __future__ import annotations

from app.modules.mcc.domain.entities import Mcc
from app.modules.mcc.infrastructure.models import MccModel


class MccMapper:

    __slots__ = ()

    @staticmethod
    def to_model(entity: Mcc) -> MccModel:
        return MccModel(
            id=entity.id,

            user_id=entity.user_id,

            code=entity.code,
            name=entity.name,

            mcc_type=entity.mcc_type,
            route_code=entity.route_code,

            sample_start=entity.sample_start,
            sample_end=entity.sample_end,
            visible_member=entity.visible_member,

            address_id=entity.address_id,
            bank_account_id=entity.bank_account_id,
            settings_id=entity.settings_id,
            milk_quality_config_id=entity.milk_quality_config_id,
            fixed_rate_config_id=entity.fixed_rate_config_id,

            is_active=entity.is_active,

            created_by=entity.created_by,
            updated_by=entity.updated_by,

            is_deleted=entity.is_deleted,
            deleted_at=entity.deleted_at,
            deleted_by=entity.deleted_by,

            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_entity(model: MccModel, profile_image: str | None = None, can_modify: bool = False) -> Mcc:
        return Mcc(
            id=model.id,

            user_id=model.user_id,

            code=model.code,
            name=model.name,

            mcc_type=model.mcc_type,
            route_code=model.route_code,

            sample_start=model.sample_start,
            sample_end=model.sample_end,
            visible_member=model.visible_member,

            address_id=model.address_id,
            bank_account_id=model.bank_account_id,
            settings_id=model.settings_id,
            milk_quality_config_id=model.milk_quality_config_id,
            fixed_rate_config_id=model.fixed_rate_config_id,

            profile_image=profile_image,

            is_active=model.is_active,

            is_deleted=model.is_deleted,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,

            created_by=model.created_by,
            updated_by=model.updated_by,

            created_at=model.created_at,
            updated_at=model.updated_at,
            can_modify=can_modify
        )