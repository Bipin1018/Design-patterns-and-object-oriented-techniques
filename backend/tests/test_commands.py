"""Unit tests for the command objects. Pure domain: no database, no HTTP."""

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.domain.actuators.context import ActuatorContext
from src.domain.actuators.ports import ActuatorPort
from src.domain.commands.base import InvalidCommandPayloadError
from src.domain.commands.invoker import (
    COMMAND_REGISTRY,
    CommandInvoker,
    UnknownCommandTypeError,
    command_for,
)
from src.domain.commands.light import SetLightLevelCommand
from src.domain.commands.pump import StartPumpCommand, StopPumpCommand


class RecordingPort(ActuatorPort):
    """Stands in for the decorated port. Remembers every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, dict[str, Any]]] = []

    def apply(self, device_id: UUID, command: str, payload: dict[str, Any]) -> None:
        self.calls.append((device_id, command, payload))


def test_registry_maps_each_name_to_its_class() -> None:
    assert COMMAND_REGISTRY == {
        "start_pump": StartPumpCommand,
        "stop_pump": StopPumpCommand,
        "set_light_level": SetLightLevelCommand,
    }


def test_command_for_builds_the_right_object() -> None:
    device_id = uuid4()
    command = command_for("start_pump", device_id, None)
    assert isinstance(command, StartPumpCommand)
    assert command.device_id == device_id
    assert command.payload == {}


def test_unknown_name_is_refused() -> None:
    with pytest.raises(UnknownCommandTypeError, match="open_window"):
        command_for("open_window", uuid4(), {})


@pytest.mark.parametrize("command_type", ["start_pump", "stop_pump", "set_light_level"])
def test_invoker_runs_any_command_through_the_port(command_type: str) -> None:
    device_id = uuid4()
    port = RecordingPort()

    CommandInvoker().run(command_for(command_type, device_id, {}), port)

    assert [(d, c) for d, c, _ in port.calls] == [(device_id, command_type)]


def test_light_level_defaults_to_1() -> None:
    assert command_for("set_light_level", uuid4(), {}).payload == {"level": 1}


@pytest.mark.parametrize("level", [-1, 101, 2.5, "10", True])
def test_bad_light_level_is_refused(level: object) -> None:
    with pytest.raises(InvalidCommandPayloadError):
        command_for("set_light_level", uuid4(), {"level": level})


@pytest.mark.parametrize(
    ("command_type", "device_type", "state"),
    [
        ("start_pump", "water_pump", "idle"),
        ("stop_pump", "water_pump", "running"),
        ("set_light_level", "grow_light", "idle"),
        ("set_light_level", "grow_light", "running"),
    ],
)
def test_target_state_agrees_with_the_state_machine(
    command_type: str, device_type: str, state: str
) -> None:
    target = COMMAND_REGISTRY[command_type].target_state
    assert target == ActuatorContext(device_type, state).target_for(command_type)