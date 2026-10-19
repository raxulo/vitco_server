from uuid import UUID
from pydantic import BaseModel


class FixedRateConfigResponse(BaseModel):

    id: UUID
    user_id: UUID
    fixed_rate: float
    less_detection: float
    high_detection: float
    min_fat: float
    max_fat: float
    min_snf: float
    max_snf: float

    class Config:
        from_attributes = True