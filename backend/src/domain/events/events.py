"""Events: small records of something that already happened.

A publisher creates one and gives it to the bus. It doesn't know who listens.
location_id and zone_id come from the device, and are None if it has no zone.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ReadingCreated:
    """A reading was saved for a tracked device."""

    event_type: ClassVar[str] = "reading.created"

    device_id: UUID
    location_id: UUID | None
    zone_id: UUID | None
    value: float
    unit: str  # "vwc" or "lux"
    source: str  # "simulation", "vendor" or "mqtt"
    recorded_at: datetime


@dataclass(frozen=True, kw_only=True)
class ThresholdCrossed:
    """Moisture went below the zone's low threshold."""

    event_type: ClassVar[str] = "threshold.crossed"

    device_id: UUID | None
    location_id: UUID | None
    zone_id: UUID | None
    moisture: float
    threshold_low: float
    recorded_at: datetime


@dataclass(frozen=True, kw_only=True)
class CommandFailed:
    """A command was allowed, but the actuator couldn't run it."""

    event_type: ClassVar[str] = "command.failed"

    device_id: UUID | None
    location_id: UUID | None
    zone_id: UUID | None
    command_type: str
    message: str  # e.g. "Max run time exceeded"


@dataclass(frozen=True, kw_only=True)
class ActuatorStateChanged:
    """An actuator's new state was saved."""

    event_type: ClassVar[str] = "state.changed"

    device_id: UUID | None
    location_id: UUID | None
    zone_id: UUID | None
    previous_state: str
    state: str


@dataclass(frozen=True, kw_only=True)
class AlertCreated:
    """An alert was saved. Phase 12 sends this to the dashboard."""

    event_type: ClassVar[str] = "alert.created"

    alert_id: UUID
    device_id: UUID | None
    location_id: UUID | None
    zone_id: UUID | None
    severity: str
    message: str
    alert_event_type: str  # what caused it, e.g. "threshold.crossed"
    status: str
    created_at: datetime