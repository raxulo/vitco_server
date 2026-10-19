from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True,kw_only=True)
class CreateFixedRateConfigCommand:
    
    user_id: UUID | None = None

    fixed_rate: float = 0.0
    less_detection: float = 0.0
    high_detection: float = 0.0
    min_fat: float = 0.0
    max_fat: float = 0.0
    min_snf: float = 0.0
    max_snf: float = 0.0


@dataclass(slots=True, kw_only=True)
class UpdateFixedRateConfigCommand:

    id: UUID | None = None
    user_id: UUID | None = None

    fixed_rate: float = 0.0
    less_detection: float = 0.0
    high_detection: float = 0.0
    min_fat: float = 0.0
    max_fat: float = 0.0
    min_snf: float = 0.0
    max_snf: float = 0.0


@dataclass(slots=True, frozen=True)
class GetFixedRateConfigQuery:

    id: UUID


@dataclass(slots=True, frozen=True)
class GetFixedRateConfigByUserQuery:

    user_id: UUID


@dataclass(slots=True, frozen=True)
class DeleteFixedRateConfigCommand:

    id: UUID