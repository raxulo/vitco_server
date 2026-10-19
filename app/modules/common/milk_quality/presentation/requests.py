from pydantic import BaseModel, Field


class CreateMilkQualityConfigRequest(BaseModel):

    cow_min_fat: float = Field(default=0.0, ge=0.0)
    cow_max_fat: float = Field(default=0.0, ge=0.0)
    cow_min_snf: float = Field(default=0.0, ge=0.0)
    cow_max_snf: float = Field(default=0.0, ge=0.0)

    buffalo_min_fat: float = Field(default=0.0, ge=0.0)
    buffalo_max_fat: float = Field(default=0.0, ge=0.0)
    buffalo_min_snf: float = Field(default=0.0, ge=0.0)
    buffalo_max_snf: float = Field(default=0.0, ge=0.0)


class UpdateMilkQualityConfigRequest(BaseModel):

    cow_min_fat: float | None = Field(None, ge=0.0)
    cow_max_fat: float | None = Field(None, ge=0.0)
    cow_min_snf: float | None = Field(None, ge=0.0)
    cow_max_snf: float | None = Field(None, ge=0.0)

    buffalo_min_fat: float | None = Field(None, ge=0.0)
    buffalo_max_fat: float | None = Field(None, ge=0.0)
    buffalo_min_snf: float | None = Field(None, ge=0.0)
    buffalo_max_snf: float | None = Field(None, ge=0.0)