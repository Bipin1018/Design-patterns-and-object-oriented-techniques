"""Request and response shapes for the locations API."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ZoneInputDto(BaseModel):
    """One zone as the client sends it, on create or on zone add/edit."""

    name: str
    moisture_threshold_low: float
    moisture_threshold_high: float
    schedule: dict[str, Any] = Field(default_factory=dict)


class BuildLocationConfigRequestDto(BaseModel):
    """Body of POST /api/locations/config."""

    location_name: str
    zones: list[ZoneInputDto]


class LocationSummaryDto(BaseModel):
    """One row of GET /api/locations."""

    id: UUID
    name: str


class ZoneDto(BaseModel):
    """A saved zone. Always carries location_id, never greenhouse_id."""

    id: UUID
    location_id: UUID
    name: str
    moisture_threshold_low: float
    moisture_threshold_high: float
    schedule: dict[str, Any]


class LocationConfigDto(BaseModel):
    """A location with its zones."""

    location: LocationSummaryDto
    zones: list[ZoneDto]