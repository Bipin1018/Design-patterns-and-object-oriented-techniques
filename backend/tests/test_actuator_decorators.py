"""Unit tests for the actuator decorators. No database, no HTTP."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.domain.actuators.policies import (
    MAX_RUN_TIME_EXCEEDED,
    ActuatorPolicyError,
    max_run_time_exceeded,
)
from src.domain.actuators.ports import ActuatorPort, ExecutionLogPort
from src.infrastructure.adapters.actuators.logging_decorator import LoggingActuatorDecorator
from src.infrastructure.adapters.actuators.max_runtime_decorator import MaxRunTimeActuatorDecorator
from src.infrastructure.persistence.actuator_state_repository import StoredState

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


class SpyPort(ActuatorPort):
    """Fake innermost adapter. Remembers every call, or fails if told to."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self._error = error

    def apply(self, device_id: UUID, command: str, payload: dict[str, Any]) -> None:
        self.calls.append(command)
        if self._error is not None:
            raise self._error


class FakeLog(ExecutionLogPort):
    """Keeps rows in a list instead of the database."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record(
        self,
        device_id: UUID,
        *,
        success: bool,
        policy_applied: list[str],
        message: str | None,
    ) -> None:
        self.rows.append(
            {"success": success, "policy_applied": policy_applied, "message": message}
        )


class FakeStates:
    """Says the actuator has been in `state` for `minutes`."""

    def __init__(self, state: str | None = None, minutes: int = 0) -> None:
        self._stored = (
            None
            if state is None
            else StoredState(
                device_id=uuid4(), state=state, updated_at=NOW - timedelta(minutes=minutes)
            )
        )

    def get(self, device_id: UUID) -> StoredState | None:
        return self._stored


def build(
    states: FakeStates, inner: SpyPort | None = None
) -> tuple[ActuatorPort, SpyPort, FakeLog]:
    """Same order as the app: logging, then max run time, then the adapter."""
    inner = inner or SpyPort()
    log = FakeLog()
    max_run = MaxRunTimeActuatorDecorator(inner, states, clock=lambda: NOW)
    return LoggingActuatorDecorator(max_run, log), inner, log


# -- the rule ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "minutes", "blocked"),
    [
        ("running", 30, True),
        ("running", 90, True),
        ("running", 29, False),
        ("idle", 600, False),
        ("maintenance", 600, False),
    ],
)
def test_max_run_time_rule(state: str, minutes: int, blocked: bool) -> None:
    assert max_run_time_exceeded(state, NOW - timedelta(minutes=minutes), NOW) is blocked


# -- each decorator alone ---------------------------------------------------


def test_decorators_share_actuator_port() -> None:
    max_run = MaxRunTimeActuatorDecorator(SpyPort(), FakeStates())
    outer = LoggingActuatorDecorator(max_run, FakeLog())

    assert isinstance(max_run, ActuatorPort)
    assert isinstance(outer, ActuatorPort)


def test_max_runtime_does_not_call_inner() -> None:
    inner = SpyPort()
    port = MaxRunTimeActuatorDecorator(inner, FakeStates("running", 30), clock=lambda: NOW)

    with pytest.raises(ActuatorPolicyError) as caught:
        port.apply(uuid4(), "stop_pump", {})

    assert inner.calls == []
    assert caught.value.policy == "maxRunTime"
    assert str(caught.value) == MAX_RUN_TIME_EXCEEDED


def test_max_runtime_lets_a_short_run_through() -> None:
    inner = SpyPort()
    port = MaxRunTimeActuatorDecorator(inner, FakeStates("running", 29), clock=lambda: NOW)

    port.apply(uuid4(), "stop_pump", {})

    assert inner.calls == ["stop_pump"]


def test_max_runtime_with_no_stored_state_passes() -> None:
    inner = SpyPort()
    port = MaxRunTimeActuatorDecorator(inner, FakeStates(None), clock=lambda: NOW)

    port.apply(uuid4(), "start_pump", {})

    assert inner.calls == ["start_pump"]


# -- the full chain ---------------------------------------------------------


def test_logging_records_success_even_for_an_unknown_command() -> None:
    port, inner, log = build(FakeStates("idle", 600))

    port.apply(uuid4(), "not_a_real_command", {})

    assert inner.calls == ["not_a_real_command"]
    assert log.rows == [{"success": True, "policy_applied": ["logging"], "message": None}]


def test_failed_policy_writes_execution_row() -> None:
    port, inner, log = build(FakeStates("running", 31))

    with pytest.raises(ActuatorPolicyError):
        port.apply(uuid4(), "stop_pump", {})

    assert inner.calls == []
    assert log.rows == [
        {
            "success": False,
            "policy_applied": ["maxRunTime", "logging"],
            "message": "Max run time exceeded",
        }
    ]


def test_logging_records_adapter_failure_and_reraises() -> None:
    port, _, log = build(FakeStates("idle"), SpyPort(error=RuntimeError("relay stuck")))

    with pytest.raises(RuntimeError, match="relay stuck"):
        port.apply(uuid4(), "start_pump", {})

    assert log.rows == [{"success": False, "policy_applied": ["logging"], "message": "relay stuck"}]