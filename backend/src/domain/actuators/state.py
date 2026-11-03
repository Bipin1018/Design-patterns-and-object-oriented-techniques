"""Actuator lifecycle: the states, the legal edges, and what each move is called.

This file is the whole rulebook. If an edge is not in TRANSITIONS it is
illegal, and nothing else in the app gets to decide otherwise.

Plain Python on purpose. No SQLAlchemy, no FastAPI, no Pydantic, so the tests
for it need no database.
"""

OFF = "off"
IDLE = "idle"
RUNNING = "running"
ERROR = "error"
MAINTENANCE = "maintenance"

ACTUATOR_STATES: tuple[str, ...] = (OFF, IDLE, RUNNING, ERROR, MAINTENANCE)

# Where every actuator starts: after the migration seed, and after provisioning.
INITIAL_STATE = IDLE

# The transition table. Key: the current state. Value: the states it may move to.
# Staying in the same state is not an edge, so idle -> idle is illegal too.
TRANSITIONS: dict[str, frozenset[str]] = {
    OFF: frozenset({IDLE, ERROR}),
    IDLE: frozenset({RUNNING, OFF, MAINTENANCE, ERROR}),
    RUNNING: frozenset({IDLE, ERROR}),
    ERROR: frozenset({IDLE, MAINTENANCE}),
    MAINTENANCE: frozenset({IDLE, OFF, ERROR}),
}

# The order targets and commands are listed in, so the API answer is stable.
_TARGET_ORDER: tuple[str, ...] = (RUNNING, IDLE, OFF, MAINTENANCE, ERROR)

# Edges a person can ask for, and what each request is called. Edges into ERROR
# are missing on purpose: a fault is reported by the device, nobody orders one.
_EDGE_COMMANDS: dict[tuple[str, str], str] = {
    (OFF, IDLE): "power_on",
    (IDLE, OFF): "power_off",
    (MAINTENANCE, OFF): "power_off",
    (IDLE, MAINTENANCE): "start_maintenance",
    (ERROR, MAINTENANCE): "start_maintenance",
    (MAINTENANCE, IDLE): "finish_maintenance",
    (ERROR, IDLE): "reset",
}

# idle <-> running is named after the device, so Phase 10 can say start_pump.
_RUN_COMMANDS: dict[str, tuple[str, str]] = {
    "water_pump": ("start_pump", "stop_pump"),
    "grow_light": ("turn_on_light", "turn_off_light"),
}
_GENERIC_RUN_COMMANDS: tuple[str, str] = ("start", "stop")


class ActuatorStateError(ValueError):
    """Base for every actuator state problem."""


class UnknownStateError(ActuatorStateError):
    """The name is not one of ACTUATOR_STATES. The API answers 400."""


class IllegalTransitionError(ActuatorStateError):
    """The edge is not in TRANSITIONS. The API answers 409 and nothing is saved."""

    def __init__(self, current: str, target: str) -> None:
        allowed = ", ".join(targets_from(current)) or "none"
        super().__init__(
            f"Cannot go from {current} to {target}. "
            f"From {current} the allowed targets are: {allowed}."
        )
        self.current = current
        self.target = target


class CommandNotAllowedError(ActuatorStateError):
    """The command does not lead anywhere from the current state."""


def validate_state(name: str) -> str:
    """Return the name if it is a known state, otherwise raise."""
    if name not in TRANSITIONS:
        valid = ", ".join(ACTUATOR_STATES)
        raise UnknownStateError(f"Unknown actuator state {name!r}. Valid states: {valid}.")
    return name


def targets_from(current: str) -> list[str]:
    """Every state reachable in one move from current, in a fixed order."""
    allowed = TRANSITIONS[validate_state(current)]
    return [target for target in _TARGET_ORDER if target in allowed]


def commands_for(device_type: str) -> dict[tuple[str, str], str]:
    """Command name for each edge a person can ask for, for this kind of actuator."""
    start, stop = _RUN_COMMANDS.get(device_type, _GENERIC_RUN_COMMANDS)
    return {**_EDGE_COMMANDS, (IDLE, RUNNING): start, (RUNNING, IDLE): stop}