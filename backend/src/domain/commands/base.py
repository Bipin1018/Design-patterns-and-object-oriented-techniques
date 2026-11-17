"""Command: one request to an actuator, packaged as an object.

A command knows three things: which device it is for, what it carries
(payload), and how to carry itself out through an ActuatorPort. It also says
which state the actuator should be in afterwards, so the service can decide
whether a transition is needed.

Plain Python, like the state machine. No SQLAlchemy, no FastAPI.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar
from uuid import UUID

from src.domain.actuators.ports import ActuatorPort

# What lands in command_log.status.
SUCCESS = "success"
FAILED = "failed"
REJECTED = "rejected"


class InvalidCommandPayloadError(ValueError):
    """The payload does not fit the command, e.g. a light level of 500. The API answers 400."""


@dataclass(frozen=True)
class CommandResult:
    """How one command ended: success, failed or rejected, and why if not success."""

    status: str
    error_message: str | None = None


@dataclass
class Command(ABC):
    """Base class. Each subclass sets command_type and target_state."""

    device_id: UUID
    payload: dict[str, Any] = field(default_factory=dict)

    # Set on each subclass, not passed in.
    command_type: ClassVar[str]
    # The state the actuator should be in after a successful execute.
    target_state: ClassVar[str]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Check the payload. Override when a command needs one. Raise on bad input."""
        return  # most commands carry no payload, so nothing to check

    @abstractmethod
    def execute(self, port: ActuatorPort) -> None:
        """Carry the command out through the (decorated) port."""