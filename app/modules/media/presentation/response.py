from uuid import UUID
from pydantic import BaseModel
from app.modules.vlcc.domain.enums import CollectionMode


class VlccResponse(BaseModel):

    id: UUID
    user_id: UUID
    uic_code: str
    vlcc_code: str
    name: str
    contact_person: str | None
    address_id: UUID | None
    bank_account_id: UUID | None
    milk_quality_config_id: UUID | None
    settings_id: UUID | None
    profile_image: str | None
    entry_mode: CollectionMode
    route_code: int | None
    soc_percentage: float
    farmer_enabled: bool
    is_active: bool

    class Config:
        from_attributes = True