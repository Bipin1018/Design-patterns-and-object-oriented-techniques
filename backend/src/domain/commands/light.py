"""Grow light commands."""

from dataclasses import dataclass
from typing import ClassVar

from src.domain.actuators.ports import ActuatorPort
from src.domain.actuators.state import RUNNING
from src.domain.commands.base import Command, InvalidCommandPayloadError

MIN_LEVEL = 0
MAX_LEVEL = 100
DEFAULT_LEVEL = 1


@dataclass
class SetLightLevelCommand(Command):
    command_type: ClassVar[str] = "set_light_level"
    # From idle this switches the light on. From running the state is already
    # running, so the service sees no difference and does not transition.
    target_state: ClassVar[str] = RUNNING

    def validate(self) -> None:
        level = self.payload.get("level", DEFAULT_LEVEL)
        # bool is a subclass of int in Python, so True would pass as 1 without this.
        if isinstance(level, bool) or not isinstance(level, int):
            raise InvalidCommandPayloadError("payload.level must be a whole number.")
        if not MIN_LEVEL <= level <= MAX_LEVEL:
            raise InvalidCommandPayloadError(
                f"payload.level must be between {MIN_LEVEL} and {MAX_LEVEL}, got {level}."
            )
        # Store the level actually used, so the log shows {"level": 1} even when
        # the client sent {}.
        self.payload = {**self.payload, "level": level}

    def execute(self, port: ActuatorPort) -> None:
        port.apply(self.device_id, self.command_type, self.payload)