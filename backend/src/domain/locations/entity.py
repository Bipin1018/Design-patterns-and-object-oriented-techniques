"""Location entities.

Plain Python: no SQLAlchemy, no Pydantic, no FastAPI. Frozen, because once
build() has checked a config nothing downstream should alter it.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Zone:
    id: UUID | None = None  # None until the repository saves it
    name: str
    moisture_threshold_low: float
    moisture_threshold_high: float
    schedule: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class Location:
    id: UUID | None = None
    name: str
    zones: tuple[Zone, ...] = ()


@dataclass(frozen=True, kw_only=True)
class LocationConfig:
    """What build() returns: a location with its zones, checked and unsaved."""

    location: Location