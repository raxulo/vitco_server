from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class CreateMilkQualityConfigCommand(BaseModel):

    user_id: UUID | None = None

    cow_min_fat: float = Field(default=0.0, ge=0)
    cow_max_fat: float = Field(default=0.0, ge=0)

    cow_min_snf: float = Field(default=0.0, ge=0)
    cow_max_snf: float = Field(default=0.0, ge=0)

    buffalo_min_fat: float = Field(default=0.0, ge=0)
    buffalo_max_fat: float = Field(default=0.0, ge=0)

    buffalo_min_snf: float = Field(default=0.0, ge=0)
    buffalo_max_snf: float = Field(default=0.0, ge=0)


class UpdateMilkQualityConfigCommand(
    CreateMilkQualityConfigCommand
):

    id: UUID | None = None


class GetMilkQualityConfigQuery(BaseModel):

    id: UUID


class GetMilkQualityConfigByUserQuery(BaseModel):

    user_id: UUID


class DeleteMilkQualityConfigCommand(BaseModel):

    id: UUID