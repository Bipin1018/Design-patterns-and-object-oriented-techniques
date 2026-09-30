"""The actuator port.

The mirror image of SensorPort. A sensor is asked for a value; an actuator is
told to do something.

Phase 5 only defines the port and a simulation adapter behind it. Phase 9 wraps
this same port with decorators for retry and logging, and Phase 10 drives it
from the command side. Defining it now is what makes those phases additions
rather than rewrites.

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

        Raises AdapterError if the device cannot accept commands this way.
        """