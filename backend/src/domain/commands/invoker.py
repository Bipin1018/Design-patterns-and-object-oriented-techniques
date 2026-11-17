"""The registry and the invoker.

The registry maps a command_type string to its class. The invoker runs a
command. Neither of them ever asks which command it is holding: there is no
if command_type == "start_pump" anywhere. A new command is one new class and
one new line in COMMAND_CLASSES.
"""

from typing import Any
from uuid import UUID

from src.domain.actuators.ports import ActuatorPort
from src.domain.commands.base import Command
from src.domain.commands.light import SetLightLevelCommand
from src.domain.commands.pump import StartPumpCommand, StopPumpCommand

COMMAND_CLASSES: tuple[type[Command], ...] = (
    StartPumpCommand,
    StopPumpCommand,
    SetLightLevelCommand,
)

COMMAND_REGISTRY: dict[str, type[Command]] = {cls.command_type: cls for cls in COMMAND_CLASSES}


class UnknownCommandTypeError(ValueError):
    """No command class for that name. The API answers 400 and writes no row."""


def command_for(command_type: str, device_id: UUID, payload: dict[str, Any] | None) -> Command:
    """Look the name up and build the command. Raises on an unknown name or bad payload."""
    command_class = COMMAND_REGISTRY.get(command_type)
    if command_class is None:
        known = ", ".join(COMMAND_REGISTRY)
        raise UnknownCommandTypeError(
            f"Unknown command_type {command_type!r}. Known commands: {known}."
        )
    return command_class(device_id=device_id, payload=dict(payload or {}))


class CommandInvoker:
    """Runs any command against a port, without knowing which command it is."""

    def run(self, command: Command, port: ActuatorPort) -> None:
        command.execute(port)