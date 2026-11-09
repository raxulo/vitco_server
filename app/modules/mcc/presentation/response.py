from uuid import UUID
from pydantic import BaseModel
from app.modules.mcc.domain.enums import MccType


class MccResponse(BaseModel):

    id: UUID
    user_id: UUID
    code: str
    name: str
    mcc_type: MccType
    route_code: int | None
    sample_start: int | None
    sample_end: int | None
    visible_member: bool = True
    address_id: UUID | None
    bank_account_id: UUID | None
    dairy_config_id: UUID | None
    rate_config_id: UUID | None
    profile_image: str | None
    is_active: bool

    class Config:
        from_attributes = True