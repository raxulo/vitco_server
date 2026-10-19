from uuid import UUID
from pydantic import BaseModel
from app.modules.farmer.domain.enums import MilkType


class FarmerResponse(BaseModel):

    id: UUID
    user_id: UUID
    farmer_code: str
    name: str
    vlcc_id: UUID | None
    address_id: UUID | None
    bank_account_id: UUID | None
    milk_type: MilkType
    assigned_chart_rank: int = 1
    profile_image: str | None
    sms_enabled: bool
    is_active: bool

    class Config:
        from_attributes = True