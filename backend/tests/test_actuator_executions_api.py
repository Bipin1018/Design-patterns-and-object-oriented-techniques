"""API tests for the execution log. These need the stack up."""

from collections.abc import Iterator
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import delete, func, select, update

from src.infrastructure.adapters.actuators.selector import _SIMULATION
from src.infrastructure.db import SessionLocal
from src.infrastructure.persistence.models import (
    ActuatorExecutionLogRow,
    ActuatorStateRow,
    DeviceRow,
)
from src.main import app

client = TestClient(app)

MISSING = "00000000-0000-0000-0000-000000000000"


def apply(device_id: str, command: str) -> Response:
    return client.post(f"/api/actuators/{device_id}/apply", json={"command": command})


def log_rows(device_id: str) -> list[tuple[bool, list[str], str | None]]:
    """Read the table directly, oldest first."""
    log = ActuatorExecutionLogRow
    with SessionLocal() as session:
        rows = session.execute(
            select(log.success, log.policy_applied, log.message)
            .where(log.device_id == UUID(device_id))
            .order_by(log.created_at)
        ).all()
    return [(success, policies, message) for success, policies, message in rows]


def running_for(device_id: str, minutes: int) -> None:
    """Make the actuator look like it started running `minutes` ago."""
    response = client.post(f"/api/devices/{device_id}/transition", json={"target": "running"})
    assert response.status_code == 200
    with SessionLocal() as session:
        session.execute(
            update(ActuatorStateRow)
            .where(ActuatorStateRow.device_id == UUID(device_id))
            .values(updated_at=func.now() - timedelta(minutes=minutes))
        )
        session.commit()


@pytest.fixture
def kit() -> Iterator[dict[str, dict]]:
    """A fresh simulation kit, deleted afterwards. CASCADE removes its log rows too."""
    response = client.post("/api/devices/provision?family=simulation")
    assert response.status_code == 201
    devices = response.json()
    ids = [UUID(device["id"]) for device in devices]

    yield {device["device_type"]: device for device in devices}

    with SessionLocal() as session:
        session.execute(delete(DeviceRow).where(DeviceRow.id.in_(ids)))
        session.commit()


def test_apply_writes_a_success_row(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]

    response = apply(pump, "not_a_real_command")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["policy_applied"] == ["logging"]
    assert body["message"] is None
    assert log_rows(pump) == [(True, ["logging"], None)]


def test_blocked_apply_is_409_and_still_logged(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    running_for(pump, 31)
    calls_before = len(_SIMULATION.applied)

    response = apply(pump, "stop_pump")

    assert response.status_code == 409
    assert response.json()["detail"] == "Max run time exceeded"
    assert len(_SIMULATION.applied) == calls_before  # the real adapter was never reached
    assert log_rows(pump) == [(False, ["maxRunTime", "logging"], "Max run time exceeded")]


def test_running_under_30_minutes_is_allowed(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    running_for(pump, 5)

    assert apply(pump, "stop_pump").status_code == 200
    assert log_rows(pump) == [(True, ["logging"], None)]


def test_executions_endpoint_lists_newest_first(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    assert apply(pump, "first").status_code == 200
    running_for(pump, 31)
    assert apply(pump, "second").status_code == 409

    response = client.get(f"/api/actuators/executions?limit=20&device_id={pump}")

    assert response.status_code == 200
    rows = response.json()
    assert [row["success"] for row in rows] == [False, True]
    assert set(rows[0]) == {"id", "device_id", "success", "policy_applied", "message", "created_at"}


def test_executions_limit(kit: dict[str, dict]) -> None:
    light = kit["grow_light"]["id"]
    for _ in range(3):
        assert apply(light, "turn_on_light").status_code == 200

    response = client.get(f"/api/actuators/executions?limit=2&device_id={light}")

    assert len(response.json()) == 2
    assert client.get("/api/actuators/executions?limit=0").status_code == 422


def test_missing_actuator_or_sensor_is_404_and_writes_nothing(kit: dict[str, dict]) -> None:
    sensor = kit["moisture_sensor"]["id"]

    assert apply(MISSING, "start_pump").status_code == 404
    assert apply(sensor, "start_pump").status_code == 404
    assert log_rows(sensor) == []