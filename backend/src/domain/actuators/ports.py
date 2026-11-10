"""The actuator ports.

ActuatorPort is the mirror image of SensorPort. A sensor is asked for a value;
an actuator is told to do something.

Phase 5 defined ActuatorPort and a simulation adapter behind it. Phase 9 wraps
that same port with decorators (logging, max run time) and adds
ExecutionLogPort, where the logging decorator records each attempt. Phase 10
drives the decorated port from the command side.

apply returns None on purpose. "Did the pump start" is a question about state,
and state is not this port's job.
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class ActuatorPort(ABC):
    @abstractmethod
    def apply(self, device_id: UUID, command: str, payload: dict[str, Any]) -> None:
        """Send one command to a device.

        Raises AdapterError if the device cannot accept commands this way, and
        ActuatorPolicyError if a decorator's policy refuses the command.
        """


class ExecutionLogPort(ABC):
    """Where the logging decorator records each attempt.

    A port, so the decorator depends on "somewhere rows go", not on SQLAlchemy.
    The real one is ExecutionLogRepository. The unit tests pass an in-memory fake.
    """

    @abstractmethod
    def record(
        self,
        device_id: UUID,
        *,
        success: bool,
        policy_applied: list[str],
        message: str | None,
    ) -> None:
        """Store one attempt, successful or not."""