from typing import Any
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.vlcc.domain.dto import VlccDto
from app.modules.vlcc.domain.enums import VlccType
from app.modules.vlcc.application.command import CreateVlcc, CreateVlccCommand
from app.modules.vlcc.domain.entities import Vlcc
from app.modules.vlcc.infrastructure.models import VlccModel


class VlccMapper:

    @staticmethod
    def _parse_vlcc_type(val: Any) -> VlccType:
        if val is None:
            return VlccType.NORMAL
        if isinstance(val, VlccType):
            return val
        try:
            return VlccType(int(val))
        except (ValueError, TypeError):
            return (
                VlccType.VLCC_FARMER_TYPE
                if str(val).strip().upper() in ("VLCC_FARMER_TYPE", "1")
                else VlccType.NORMAL
            )

    @staticmethod
    def to_entity(
        model: VlccModel,
        owner_name: str | None = None,
        setting: SettingsModel | None = None,
        route_name: str | None = None,
        profile_image: str | None = None,
        can_modify: bool = False,
        city: str | None = None,
    ) -> Vlcc:
        return Vlcc(
            id=model.id,
            user_id=model.user_id,
            uic_code=model.uic_code,
            vlcc_code=model.vlcc_code,
            name=model.name,
            contact_person=model.contact_person,
            address_id=model.address_id,
            bank_account_id=model.bank_account_id,
            milk_quality_config_id=model.milk_quality_config_id,
            settings_id=model.settings_id,
            profile_image=profile_image,
            entry_mode=model.entry_mode,
            route_code=model.route_code,
            soc_percentage=model.soc_percentage,
            farmer_enabled=model.farmer_enabled,
            is_active=model.is_active,
            assigned_chart_rank=model.assigned_chart_rank,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            owner_name=owner_name,
            analyzer_collection_mode=setting.analyzer_collection_mode if setting else None,
            weight_collection_mode=setting.weight_collection_mode if setting else None,
            route_name=route_name,
            can_modify=can_modify,
            is_deleted=model.is_deleted,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
            city=city,
            vlcc_type=VlccMapper._parse_vlcc_type(getattr(model, "vlcc_type", VlccType.NORMAL)),
        )

    @staticmethod
    def entity_to_model(entity: Vlcc) -> VlccModel:
        return VlccModel(
            id=entity.id,
            user_id=entity.user_id,
            uic_code=entity.uic_code,
            vlcc_code=entity.vlcc_code,
            name=entity.name,
            contact_person=entity.contact_person,
            address_id=entity.address_id,
            bank_account_id=entity.bank_account_id,
            milk_quality_config_id=entity.milk_quality_config_id,
            settings_id=entity.settings_id,
            entry_mode=entity.entry_mode,
            route_code=entity.route_code,
            soc_percentage=entity.soc_percentage,
            farmer_enabled=entity.farmer_enabled,
            is_active=entity.is_active,
            assigned_chart_rank=entity.assigned_chart_rank,
            created_by=entity.created_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
            deleted_at=entity.deleted_at,
            deleted_by=entity.deleted_by,
            vlcc_type=VlccMapper._parse_vlcc_type(getattr(entity, "vlcc_type", VlccType.NORMAL)),
        )

    @staticmethod
    def to_model(data: CreateVlcc) -> VlccModel:
        return VlccModel(
            user_id=data.user_id,
            uic_code=data.uic_code,
            vlcc_code=data.vlcc_code,
            name=data.name,
            contact_person=data.contact_person,
            address_id=data.address_id,
            bank_account_id=data.bank_account_id,
            milk_quality_config_id=data.milk_quality_config_id,
            settings_id=data.settings_id,
            entry_mode=data.entry_mode,
            route_code=data.route_code,
            soc_percentage=data.soc_percentage,
            farmer_enabled=data.farmer_enabled,
            is_active=data.is_active,
            assigned_chart_rank=data.assigned_chart_rank,
            created_by=data.created_by,
            vlcc_type=VlccMapper._parse_vlcc_type(getattr(data, "vlcc_type", VlccType.NORMAL)),
        )

    @staticmethod
    def to_dto(entity: Vlcc) -> VlccDto:
        return VlccDto(
            id=entity.id,
            user_id=entity.user_id,
            uic_code=entity.uic_code,
            vlcc_code=entity.vlcc_code,
            name=entity.name,
            contact_person=entity.contact_person,
            address_id=entity.address_id,
            bank_account_id=entity.bank_account_id,
            milk_quality_config_id=entity.milk_quality_config_id,
            settings_id=entity.settings_id,
            profile_image=entity.profile_image,
            entry_mode=entity.entry_mode,
            route_code=entity.route_code,
            route_name=entity.route_name,
            soc_percentage=entity.soc_percentage,
            farmer_enabled=entity.farmer_enabled,
            is_active=entity.is_active,
            assigned_chart_rank=entity.assigned_chart_rank,
            can_modify=entity.can_modify,
            vlcc_type=VlccMapper._parse_vlcc_type(getattr(entity, "vlcc_type", VlccType.NORMAL)),
        )
