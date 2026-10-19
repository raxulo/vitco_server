from uuid import UUID
from pydantic import BaseModel


class UnitMasterResponse(BaseModel):

    id: UUID
    name: str
    is_active: bool

    class Config:
        from_attributes = True