from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from app.modules.vlcc.domain.enums import CollectionMode


class CreateVlccRequest(BaseModel):

    uic_code: str = Field(..., min_length=1, max_length=50)
    vlcc_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    # Any password is accepted (any case, length or characters)
    password: str = Field(..., min_length=1, max_length=128)
    contact_person: str | None = Field(None, max_length=150)
    address_id: UUID | None = None
    bank_account_id: UUID | None = None
    milk_quality_config_id: UUID | None = None
    settings_id: UUID | None = None
    profile_image: str | None = None
    entry_mode: CollectionMode = Field(default=CollectionMode.MANUAL)
    route_code: int | None = None
    soc_percentage: float = Field(default=0.0, ge=0.0)
    farmer_enabled: bool = True


class UpdateVlccRequest(BaseModel):

    uic_code: str = Field(..., min_length=1, max_length=50)
    vlcc_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    password: str | None = Field(None, min_length=1, max_length=128)
    contact_person: str | None = Field(None, max_length=150)
    address_id: UUID | None = None
    bank_account_id: UUID | None = None
    milk_quality_config_id: UUID | None = None
    settings_id: UUID | None = None
    profile_image: str | None = None
    entry_mode: CollectionMode
    route_code: int | None = None
    soc_percentage: float = Field(..., ge=0.0)
    farmer_enabled: bool
    is_active: bool