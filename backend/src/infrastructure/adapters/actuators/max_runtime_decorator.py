"""Max-run-time decorator. Blocks commands once an actuator has run for 30 minutes."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from src.domain.actuators.policies import (
    MAX_RUN_TIME_EXCEEDED,
    POLICY_MAX_RUN_TIME,
    ActuatorPolicyError,
    max_run_time_exceeded,
)
from src.domain.actuators.ports import ActuatorPort
from src.infrastructure.persistence.actuator_state_repository import StoredState


class StateLookup(Protocol):
    """ActuatorStateRepository fits this. Tests use a fake."""

    def get(self, device_id: UUID) -> StoredState | None: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MaxRunTimeActuatorDecorator(ActuatorPort):
    def __init__(
        self,
        inner: ActuatorPort,
        states: StateLookup,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._inner = inner
        self._states = states
        self._clock = clock  # tests pass a fake time

    def apply(self, device_id: UUID, command: str, payload: dict[str, Any]) -> None:
        stored = self._states.get(device_id)
        if stored is not None and max_run_time_exceeded(
            stored.state, stored.updated_at, self._clock()
        ):
            # Blocked. Inner is never called.
            raise ActuatorPolicyError(POLICY_MAX_RUN_TIME, MAX_RUN_TIME_EXCEEDED)
        self._inner.apply(device_id, command, payload)