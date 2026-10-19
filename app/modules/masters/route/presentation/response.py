from uuid import UUID
from pydantic import BaseModel


class RouteMasterResponse(BaseModel):

    id: UUID
    route_code: int
    route_name: str
    is_active: bool

    class Config:
        from_attributes = True