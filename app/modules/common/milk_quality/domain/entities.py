from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, kw_only=True)
class MilkQualityConfig:

    id: UUID
    user_id: UUID

    cow_min_fat: float = 0.0
    cow_max_fat: float = 0.0

    cow_min_snf: float = 0.0
    cow_max_snf: float = 0.0

    buffalo_min_fat: float = 0.0
    buffalo_max_fat: float = 0.0

    buffalo_min_snf: float = 0.0
    buffalo_max_snf: float = 0.0