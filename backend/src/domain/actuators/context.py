"""ActuatorContext: one actuator's current state, and the guard on every move."""

from src.domain.actuators.state import (
    INITIAL_STATE,
    TRANSITIONS,
    CommandNotAllowedError,
    IllegalTransitionError,
    commands_for,
    targets_from,
    validate_state,
)


class ActuatorContext:
    """Holds one actuator's state. The only way to change it is transition()."""

    def __init__(self, device_type: str, state: str = INITIAL_STATE) -> None:
        self._device_type = device_type
        self._state = validate_state(state)
        self._commands = commands_for(device_type)

    @property
    def device_type(self) -> str:
        return self._device_type

    @property
    def state(self) -> str:
        return self._state

    def can_transition_to(self, target: str) -> bool:
        """True if target is one legal move away. Raises on an unknown name."""
        return validate_state(target) in TRANSITIONS[self._state]

    def transition(self, target: str) -> None:
        """Move to target, or raise and stay where you are."""
        if not self.can_transition_to(target):
            raise IllegalTransitionError(self._state, target)
        self._state = target

    def allowed_targets(self) -> list[str]:
        return targets_from(self._state)

    def allowed_commands(self) -> list[str]:
        """Command names legal right now. What the API sends as allowed_commands."""
        return [
            self._commands[(self._state, target)]
            for target in self.allowed_targets()
            if (self._state, target) in self._commands
        ]

    def target_for(self, command: str) -> str:
        """Which state a command leads to from here. Phase 10's Command will use this."""
        for target in self.allowed_targets():
            if self._commands.get((self._state, target)) == command:
                return target
        allowed = ", ".join(self.allowed_commands()) or "none"
        raise CommandNotAllowedError(
            f"{command!r} is not allowed while {self._state}. Allowed now: {allowed}."
        )