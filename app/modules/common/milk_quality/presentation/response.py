from uuid import UUID
from pydantic import BaseModel


class MilkQualityConfigResponse(BaseModel):

    id: UUID
    user_id: UUID
    cow_min_fat: float
    cow_max_fat: float
    cow_min_snf: float
    cow_max_snf: float
    buffalo_min_fat: float
    buffalo_max_fat: float
    buffalo_min_snf: float
    buffalo_max_snf: float

    class Config:
        from_attributes = True