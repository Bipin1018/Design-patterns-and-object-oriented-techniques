"""The alert words we use, and the shape GET /api/alerts returns."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

INFO = "info"
WARNING = "warning"
CRITICAL = "critical"

ACTIVE = "active"
RESOLVED = "resolved"
ALL = "all"  # only used as a filter, never saved
STATUS_FILTERS: tuple[str, ...] = (ACTIVE, RESOLVED, ALL)


class AlertDto(BaseModel):
    """One alert. acknowledged_at is saved but not sent."""

    id: UUID
    location_id: UUID | None = Field(description="Null if the device has no zone.")
    zone_id: UUID | None = Field(description="Null if the device has no zone.")
    device_id: UUID | None = Field(description="Null if the device was deleted.")
    severity: Literal["info", "warning", "critical"]
    message: str = Field(examples=["Moisture below zone low"])
    event_type: str = Field(
        description="What caused it: threshold.crossed, command.failed or state.changed.",
        examples=["threshold.crossed"],
    )
    status: Literal["active", "resolved"]
    created_at: datetime