from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.farmer.domain.entities import Farmer


class FarmerMapper:

    @staticmethod
    def to_model(entity: Farmer) -> FarmerModel:
        return FarmerModel(
            id=entity.id,
            user_id=entity.user_id,
            farmer_code=entity.farmer_code,
            vlcc_id=entity.vlcc_id,
            address_id=entity.address_id,
            bank_account_id=entity.bank_account_id,
            assigned_chart_rank=entity.assigned_chart_rank if entity.assigned_chart_rank is not None else 1,
            milk_type=entity.milk_type,
            sms_enabled=entity.sms_enabled,
            is_active=entity.is_active,
            created_by=entity.created_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at or entity.created_at,
            is_deleted=entity.is_deleted,
            deleted_at=entity.deleted_at,
            deleted_by=entity.deleted_by,
        )

    @staticmethod
    def to_entity(model: FarmerModel, name: str | None = None, vlcc_name: str | None = None, profile_image: str | None = None, can_modify: bool = False, mobile: str | None = None) -> Farmer:
        return Farmer(
            id=model.id,
            user_id=model.user_id,
            farmer_code=model.farmer_code,
            vlcc_id=model.vlcc_id,
            address_id=model.address_id,
            bank_account_id=model.bank_account_id,
            assigned_chart_rank=model.assigned_chart_rank if model.assigned_chart_rank is not None else 1,
            milk_type=model.milk_type,
            profile_image=profile_image,
            sms_enabled=model.sms_enabled,
            is_active=model.is_active,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            name=name,
            mobile=mobile,
            vlcc_name=vlcc_name,
            can_modify=can_modify,
            is_deleted=model.is_deleted,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
        )