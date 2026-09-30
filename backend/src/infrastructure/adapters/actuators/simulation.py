"""The simulation actuator adapter.

Records what it was told to do and returns. No GPIO, no relay, no pin.

Phase 9 wraps this class with decorators for retry and logging, so it is
written to be the innermost layer: it does one thing, it has no opinions, and
it never decides whether a command was a good idea. Phase 10 decides that.

The in-memory log is for tests and for the demo. It is not state the greenhouse
relies on, and it does not survive a restart.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.domain.actuators.ports import ActuatorPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AppliedCommand:
    """One command this adapter was given."""

    device_id: UUID
    command: str
    payload: dict[str, Any]
    applied_at: datetime


class SimulationActuatorAdapter(ActuatorPort):
    def __init__(self) -> None:
        self.applied: list[AppliedCommand] = []

    def apply(self, device_id: UUID, command: str, payload: dict[str, Any]) -> None:
        """Record the command. In simulation, recording it is doing it."""
        entry = AppliedCommand(
            device_id=device_id,
            command=command,
            payload=dict(payload),
            applied_at=datetime.now(UTC),
        )
        self.applied.append(entry)
        logger.info("Simulated %s on device %s with %s", command, device_id, payload)