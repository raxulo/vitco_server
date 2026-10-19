from pydantic import BaseModel, Field


class CreateFixedRateConfigRequest(BaseModel):

    fixed_rate: float = Field(default=0.0, ge=0.0)
    less_detection: float = Field(default=0.0, ge=0.0)
    high_detection: float = Field(default=0.0, ge=0.0)
    min_fat: float = Field(default=0.0, ge=0.0)
    max_fat: float = Field(default=0.0, ge=0.0)
    min_snf: float = Field(default=0.0, ge=0.0)
    max_snf: float = Field(default=0.0, ge=0.0)


class UpdateFixedRateConfigRequest(BaseModel):

    fixed_rate: float | None = Field(None, ge=0.0)
    less_detection: float | None = Field(None, ge=0.0)
    high_detection: float | None = Field(None, ge=0.0)
    min_fat: float | None = Field(None, ge=0.0)
    max_fat: float | None = Field(None, ge=0.0)
    min_snf: float | None = Field(None, ge=0.0)
    max_snf: float | None = Field(None, ge=0.0)