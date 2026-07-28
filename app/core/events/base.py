"""
Enterprise Base Event

Python 3.13+
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class Event:

    event_id: str = field(
        default_factory=lambda: uuid.uuid4().hex
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )