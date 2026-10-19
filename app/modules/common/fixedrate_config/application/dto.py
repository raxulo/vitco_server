from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, frozen=True)
class FixedRateConfigDto:

    id: UUID
    user_id: UUID

    fixed_rate: float
    less_detection: float
    high_detection: float
    min_fat: float
    max_fat: float
    min_snf: float
    max_snf: float