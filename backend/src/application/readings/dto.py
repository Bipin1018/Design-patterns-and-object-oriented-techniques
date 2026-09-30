"""The shape the readings API sends out.

Separate from the domain Reading for the same reason DeviceDto is separate from
Device: the entity is what the greenhouse means, this is what the wire looks
like, and neither should force a change on the other.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ReadingDto(BaseModel):
    device_id: UUID
    value: float
    unit: str
    source: str
    recorded_at: datetime


class UpdateSamplingRequestDto(BaseModel):
    """Body of PATCH /api/devices/{id}/sampling."""

    sampling_interval_seconds: int = Field(
        description="How often the sampler records this device. Minimum 5.",
    )
    tracking_enabled: bool = Field(
        description="False stops the sampler for this device. A manual read still works.",
    )