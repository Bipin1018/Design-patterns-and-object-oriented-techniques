"""The shape the API sends out.

Kept separate from the domain Device on purpose. The domain entity is what the
greenhouse means; this is what the wire looks like. Changing the JSON later
should not force a change to the entity, and vice versa.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Listed here so Scalar shows the five values. Which moves between them are
# legal is the domain's business (domain/actuators/state.py).
ActuatorStateName = Literal["off", "idle", "running", "error", "maintenance"]


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
    # Phase 8. Actuators only: a sensor has no lifecycle, so null and [].
    state: ActuatorStateName | None = Field(
        default=None,
        description="Lifecycle state of an actuator. Null for sensors.",
    )
    allowed_commands: list[str] = Field(
        default_factory=list,
        description="Commands legal in the current state. Empty for sensors.",
        examples=[["start_pump", "power_off", "start_maintenance"]],
    )


class ActuatorStateDto(BaseModel):
    """What GET /state and POST /transition return."""

    device_id: UUID
    state: ActuatorStateName
    allowed_commands: list[str]
    updated_at: datetime | None = Field(
        default=None,
        description="When the state last changed. Null if no row was ever stored.",
    )


class TransitionRequestDto(BaseModel):
    """Body of POST /api/devices/{id}/transition.

    A plain string, not the Literal above, so an unknown name reaches the
    domain and gets its explanation as a 400, instead of a generic 422.
    """

    target: str = Field(description="State to move to.", examples=["running"])