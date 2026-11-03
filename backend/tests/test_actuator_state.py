"""Unit tests for the actuator state machine. Pure domain: no database, no HTTP."""

import pytest

from src.domain.actuators.context import ActuatorContext
from src.domain.actuators.state import (
    ACTUATOR_STATES,
    ERROR,
    TRANSITIONS,
    CommandNotAllowedError,
    IllegalTransitionError,
    UnknownStateError,
    commands_for,
)

LEGAL = [(source, target) for source, targets in TRANSITIONS.items() for target in sorted(targets)]
ILLEGAL = [
    (source, target)
    for source in ACTUATOR_STATES
    for target in ACTUATOR_STATES
    if target not in TRANSITIONS[source]
]


def test_new_context_starts_idle() -> None:
    assert ActuatorContext("water_pump").state == "idle"


def test_idle_to_running_allowed() -> None:
    pump = ActuatorContext("water_pump", "idle")
    pump.transition("running")
    assert pump.state == "running"


def test_running_to_maintenance_rejected() -> None:
    pump = ActuatorContext("water_pump", "running")
    with pytest.raises(IllegalTransitionError):
        pump.transition("maintenance")
    assert pump.state == "running"


@pytest.mark.parametrize(("source", "target"), LEGAL)
def test_legal_edge_moves_the_state(source: str, target: str) -> None:
    actuator = ActuatorContext("water_pump", source)
    actuator.transition(target)
    assert actuator.state == target


@pytest.mark.parametrize(("source", "target"), ILLEGAL)
def test_illegal_edge_raises_and_keeps_the_state(source: str, target: str) -> None:
    actuator = ActuatorContext("water_pump", source)
    with pytest.raises(IllegalTransitionError):
        actuator.transition(target)
    assert actuator.state == source


def test_every_state_except_error_can_fault() -> None:
    for state in ACTUATOR_STATES:
        if state != ERROR:
            assert ERROR in TRANSITIONS[state], state


def test_error_leaves_only_by_reset_or_maintenance() -> None:
    assert TRANSITIONS[ERROR] == {"idle", "maintenance"}


def test_unknown_target_is_rejected() -> None:
    pump = ActuatorContext("water_pump", "idle")
    with pytest.raises(UnknownStateError):
        pump.transition("flying")
    assert pump.state == "idle"


def test_unknown_starting_state_is_rejected() -> None:
    with pytest.raises(UnknownStateError):
        ActuatorContext("water_pump", "broken")


def test_illegal_error_names_the_allowed_targets() -> None:
    with pytest.raises(IllegalTransitionError, match="allowed targets are: idle, error"):
        ActuatorContext("water_pump", "running").transition("maintenance")


def test_pump_commands_follow_the_state() -> None:
    assert ActuatorContext("water_pump", "idle").allowed_commands() == [
        "start_pump",
        "power_off",
        "start_maintenance",
    ]
    assert ActuatorContext("water_pump", "running").allowed_commands() == ["stop_pump"]


def test_light_commands_use_light_names() -> None:
    assert ActuatorContext("grow_light", "idle").allowed_commands()[0] == "turn_on_light"
    assert ActuatorContext("grow_light", "running").allowed_commands() == ["turn_off_light"]


def test_error_offers_reset_and_off_offers_power_on() -> None:
    assert ActuatorContext("water_pump", "error").allowed_commands() == [
        "reset",
        "start_maintenance",
    ]
    assert ActuatorContext("water_pump", "off").allowed_commands() == ["power_on"]


@pytest.mark.parametrize("device_type", ["water_pump", "grow_light", "unknown_actuator"])
def test_every_command_is_a_legal_edge_and_none_leads_to_error(device_type: str) -> None:
    for source, target in commands_for(device_type):
        assert target in TRANSITIONS[source]
        assert target != ERROR


def test_target_for_maps_a_command_to_its_state() -> None:
    assert ActuatorContext("water_pump", "idle").target_for("start_pump") == "running"
    assert ActuatorContext("water_pump", "error").target_for("reset") == "idle"


def test_target_for_rejects_a_command_not_allowed_now() -> None:
    with pytest.raises(CommandNotAllowedError):
        ActuatorContext("water_pump", "running").target_for("start_pump")