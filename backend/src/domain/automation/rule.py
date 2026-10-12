"""A location's saved strategy choice, as a plain value."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class AutomationRule:
    """One location's saved choice of algorithm.

    parameters is carried but not read yet. It is the seam for a tuned strategy
    later: numbers in the database rather than constants in a class.
    """

    location_id: UUID
    strategy_key: str
    parameters: dict[str, Any]
    updated_at: datetime