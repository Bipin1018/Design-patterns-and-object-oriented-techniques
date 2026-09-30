"""The Device entity.

Phase 2 had Sensor only. Phase 3 needs one type that covers sensors and
actuators, because both live in the same devices table and a family factory
returns a mix of them.

Frozen: once a factory has decided what a device is, nothing downstream should
quietly change it. The repository builds a new Device when it needs to add the
saved id.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Device:
    id: UUID | None = None  # None until the repository saves it
    device_type: str
    role: str  # "sensor" or "actuator"
    device_family: str  # "simulation" or "edge"
    display_name: str
    default_config: dict[str, Any] = field(default_factory=dict)
    # Phase 4 placement. Both None when the device is not in a zone.
    zone_id: UUID | None = None
    location_id: UUID | None = None
    # Phase 5 sampling. The sampler reads both of these to decide whether this
    # device is due. They carry the same defaults as the columns, so a factory
    # that says nothing about sampling still produces a valid device.
    sampling_interval_seconds: int = 300
    tracking_enabled: bool = True