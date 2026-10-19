from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field


class CreateItemMasterRequest(BaseModel):

    item_code: int = Field(..., gt=0)
    item_name: str = Field(..., min_length=1, max_length=150)
    unit_id: UUID
    rate: Decimal = Field(..., ge=0.0)


class UpdateItemMasterRequest(BaseModel):

    item_code: int = Field(..., gt=0)
    item_name: str = Field(..., min_length=1, max_length=150)
    unit_id: UUID
    rate: Decimal = Field(..., ge=0.0)
    is_active: bool