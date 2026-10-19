from pydantic import BaseModel, Field


class CreateRouteMasterRequest(BaseModel):

    route_code: int = Field(..., gt=0)
    route_name: str = Field(..., min_length=1, max_length=150)


class UpdateRouteMasterRequest(BaseModel):

    route_code: int = Field(..., gt=0)
    route_name: str = Field(..., min_length=1, max_length=150)
    is_active: bool