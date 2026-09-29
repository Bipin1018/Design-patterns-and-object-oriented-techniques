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