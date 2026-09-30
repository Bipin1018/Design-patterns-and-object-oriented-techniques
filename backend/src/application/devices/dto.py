"""The shape the API sends out.

Kept separate from the domain Device on purpose. The domain entity is what the
greenhouse means; this is what the wire looks like. Changing the JSON later
should not force a change to the entity, and vice versa.
"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class DeviceDto(BaseModel):
    id: UUID
    device_type: str
    role: Literal["sensor", "actuator"]
    device_family: str
    display_name: str
    default_config: dict[str, Any]
    # Where the device sits. Both null when it is unassigned.
    zone_id: UUID | None = None
    location_id: UUID | None = None
    # Phase 5 sampling, straight from the columns. Not read out of
    # default_config, which now only keeps a stale copy of the interval.
    sampling_interval_seconds: int = 300
    tracking_enabled: bool = True