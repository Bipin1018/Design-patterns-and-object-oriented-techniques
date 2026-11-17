"""Pump commands."""

from dataclasses import dataclass
from typing import ClassVar

from src.domain.actuators.ports import ActuatorPort
from src.domain.actuators.state import IDLE, RUNNING
from src.domain.commands.base import Command


@dataclass
class StartPumpCommand(Command):
    command_type: ClassVar[str] = "start_pump"
    target_state: ClassVar[str] = RUNNING

    def execute(self, port: ActuatorPort) -> None:
        port.apply(self.device_id, self.command_type, self.payload)


@dataclass
class StopPumpCommand(Command):
    command_type: ClassVar[str] = "stop_pump"
    target_state: ClassVar[str] = IDLE

    def execute(self, port: ActuatorPort) -> None:
        port.apply(self.device_id, self.command_type, self.payload)