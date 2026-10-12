"""What a strategy is allowed to see."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class LocationAutomationContext:
    """The state of one zone at the moment of deciding.

    moisture is None when the zone has no moisture sensor. That means "nothing
    to judge", never "zero moisture".
    """

    location_id: UUID
    zone_id: UUID
    zone_name: str
    moisture_low: float
    moisture_high: float
    moisture: float | None = None
    light: float | None = None
    recorded_at: datetime | None = None
    source_device_id: UUID | None = None