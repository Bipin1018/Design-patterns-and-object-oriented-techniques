"""API tests for POST and GET /api/commands. These need the stack up."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import delete, func, select, update

from src.infrastructure.db import SessionLocal
from src.infrastructure.persistence.models import (
    ActuatorExecutionLogRow,
    ActuatorStateRow,
    CommandLogRow,
    DeviceRow,
)
from src.main import app

client = TestClient(app)

MISSING = "00000000-0000-0000-0000-000000000000"
ROW_FIELDS = {"id", "command_type", "device_id", "payload", "status", "error_message", "created_at"}


def command(device_id: str, command_type: str, payload: dict | None = None) -> Response:
    body = {"command_type": command_type, "device_id": device_id, "payload": payload or {}}
    return client.post("/api/commands", json=body)


def command_rows(device_id: str) -> list[tuple[str, str]]:
    """(command_type, status) straight from command_log, oldest first."""
    log = CommandLogRow
    with SessionLocal() as session:
        rows = session.execute(
            select(log.command_type, log.status)
            .where(log.device_id == UUID(device_id))
            .order_by(log.created_at)
        ).all()
    return [(command_type, status) for command_type, status in rows]


def execution_count(device_id: str) -> int:
    with SessionLocal() as session:
        return session.execute(
            select(func.count())
            .select_from(ActuatorExecutionLogRow)
            .where(ActuatorExecutionLogRow.device_id == UUID(device_id))
        ).scalar_one()


def stored_state(device_id: str) -> tuple[str, datetime]:
    with SessionLocal() as session:
        row = session.get(ActuatorStateRow, UUID(device_id))
        assert row is not None
        return row.state, row.updated_at


def started_minutes_ago(device_id: str, minutes: int) -> None:
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


# -- The two the requirements name --------------------------------------------


def test_illegal_command_rejected_logged(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    before = stored_state(pump)

    response = command(pump, "stop_pump")  # an idle pump cannot stop

    assert response.status_code == 409
    body = response.json()
    assert set(body) == ROW_FIELDS  # same row shape as a success
    assert body["status"] == "rejected"
    assert "not allowed while idle" in body["error_message"]
    assert command_rows(pump) == [("stop_pump", "rejected")]
    assert stored_state(pump) == before  # state and updated_at untouched
    assert execution_count(pump) == 0  # never reached the port


def test_start_pump_transitions_to_running(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]

    response = command(pump, "start_pump")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["error_message"] is None
    assert stored_state(pump)[0] == "running"
    assert command_rows(pump) == [("start_pump", "success")]
    assert execution_count(pump) == 1  # went through the decorators


# -- The other rules ------------------------------------------------------------


def test_max_run_time_is_failed_and_keeps_the_state(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    assert command(pump, "start_pump").status_code == 200
    started_minutes_ago(pump, 31)
    before = stored_state(pump)

    response = command(pump, "stop_pump")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_message"] == "Max run time exceeded"
    assert stored_state(pump) == before  # still running, same updated_at
    assert command_rows(pump) == [("start_pump", "success"), ("stop_pump", "failed")]
    assert execution_count(pump) == 2  # the decorator's row is kept


def test_stop_pump_goes_back_to_idle(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    assert command(pump, "start_pump").status_code == 200

    assert command(pump, "stop_pump").json()["status"] == "success"
    assert stored_state(pump)[0] == "idle"


def test_light_level_turns_an_idle_light_on(kit: dict[str, dict]) -> None:
    light = kit["grow_light"]["id"]

    response = command(light, "set_light_level")

    assert response.json()["status"] == "success"
    assert response.json()["payload"] == {"level": 1}
    assert stored_state(light)[0] == "running"


def test_light_level_on_a_running_light_does_not_transition(kit: dict[str, dict]) -> None:
    light = kit["grow_light"]["id"]
    assert command(light, "set_light_level").status_code == 200
    before = stored_state(light)

    response = command(light, "set_light_level", {"level": 40})

    assert response.json()["status"] == "success"
    assert response.json()["payload"] == {"level": 40}
    assert stored_state(light) == before  # no transition: updated_at unchanged


def test_unknown_command_type_is_400_and_writes_nothing(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]

    assert command(pump, "open_window").status_code == 400
    assert command(kit["grow_light"]["id"], "set_light_level", {"level": 500}).status_code == 400
    assert command_rows(pump) == []
    assert command_rows(kit["grow_light"]["id"]) == []


def test_missing_actuator_or_sensor_is_404_and_writes_nothing(kit: dict[str, dict]) -> None:
    sensor = kit["moisture_sensor"]["id"]

    assert command(MISSING, "start_pump").status_code == 404
    assert command(sensor, "start_pump").status_code == 404
    assert command_rows(sensor) == []


def test_history_is_newest_first_and_includes_rejected(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    assert command(pump, "stop_pump").status_code == 409
    assert command(pump, "start_pump").status_code == 200

    response = client.get("/api/commands?limit=200")

    assert response.status_code == 200
    mine = [row for row in response.json() if row["device_id"] == pump]
    assert [(row["command_type"], row["status"]) for row in mine] == [
        ("start_pump", "success"),
        ("stop_pump", "rejected"),
    ]
    assert set(mine[0]) == ROW_FIELDS


def test_history_limit_bounds() -> None:
    assert client.get("/api/commands?limit=1").status_code == 200
    assert client.get("/api/commands?limit=0").status_code == 422
    assert client.get("/api/commands?limit=201").status_code == 422