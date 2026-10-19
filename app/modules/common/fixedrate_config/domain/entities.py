from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, kw_only=True)
class FixedRateConfig:

    id: UUID

    user_id: UUID

    fixed_rate: float = 0.0

    less_detection: float = 0.0
    high_detection: float = 0.0

    min_fat: float = 0.0
    max_fat: float = 0.0

    min_snf: float = 0.0
    max_snf: float = 0.0