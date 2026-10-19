from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel


class ItemMasterResponse(BaseModel):

    id: UUID
    item_code: int
    item_name: str
    unit_id: UUID
    rate: Decimal
    is_active: bool

    class Config:
        from_attributes = True