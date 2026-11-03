"""API tests for actuator state. These need the stack up."""

from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import delete

from src.infrastructure.db import SessionLocal
from src.infrastructure.persistence.models import ActuatorStateRow, DeviceRow
from src.main import app

client = TestClient(app)

MISSING = "00000000-0000-0000-0000-000000000000"


def stored(device_id: str) -> tuple[str, datetime] | None:
    """Read the row straight from the database, in a fresh session."""
    with SessionLocal() as session:
        row = session.get(ActuatorStateRow, UUID(device_id))
        return None if row is None else (row.state, row.updated_at)


def transition(device_id: str, target: str) -> Response:
    return client.post(f"/api/devices/{device_id}/transition", json={"target": target})


def actuators_by_id() -> dict[str, dict]:
    return {device["id"]: device for device in client.get("/api/devices?role=actuator").json()}


@pytest.fixture
def kit() -> Iterator[dict[str, dict]]:
    """A fresh simulation kit, keyed by device_type, deleted afterwards."""
    response = client.post("/api/devices/provision?family=simulation")
    assert response.status_code == 201
    devices = response.json()
    ids = [UUID(device["id"]) for device in devices]

    yield {device["device_type"]: device for device in devices}

    with SessionLocal() as session:
        session.execute(delete(DeviceRow).where(DeviceRow.id.in_(ids)))
        session.commit()


def test_provision_gives_actuators_a_stored_idle_state(kit: dict[str, dict]) -> None:
    pump, sensor = kit["water_pump"], kit["moisture_sensor"]

    assert pump["state"] == "idle"
    assert pump["allowed_commands"] == ["start_pump", "power_off", "start_maintenance"]
    row = stored(pump["id"])
    assert row is not None and row[0] == "idle"

    assert sensor["state"] is None
    assert sensor["allowed_commands"] == []
    assert stored(sensor["id"]) is None


def test_device_list_carries_state(kit: dict[str, dict]) -> None:
    listed = actuators_by_id()

    assert listed[kit["water_pump"]["id"]]["state"] == "idle"
    assert listed[kit["grow_light"]["id"]]["allowed_commands"][0] == "turn_on_light"


def test_legal_transition_updates_the_row(kit: dict[str, dict]) -> None:
    pump_id = kit["water_pump"]["id"]

    response = transition(pump_id, "running")

    assert response.status_code == 200
    assert response.json()["state"] == "running"
    assert response.json()["allowed_commands"] == ["stop_pump"]
    row = stored(pump_id)
    assert row is not None and row[0] == "running"
    assert actuators_by_id()[pump_id]["state"] == "running"
    assert client.get(f"/api/devices/{pump_id}/state").json()["state"] == "running"


def test_illegal_transition_does_not_update_row(kit: dict[str, dict]) -> None:
    pump_id = kit["water_pump"]["id"]
    assert transition(pump_id, "running").status_code == 200
    before = stored(pump_id)

    response = transition(pump_id, "maintenance")

    assert response.status_code == 409
    assert "running" in response.json()["detail"]
    assert stored(pump_id) == before  # same state and same updated_at


def test_unknown_target_is_400_and_changes_nothing(kit: dict[str, dict]) -> None:
    pump_id = kit["water_pump"]["id"]
    before = stored(pump_id)

    assert transition(pump_id, "flying").status_code == 400
    assert stored(pump_id) == before


def test_missing_actuator_or_sensor_is_404(kit: dict[str, dict]) -> None:
    assert transition(MISSING, "running").status_code == 404
    assert transition(kit["moisture_sensor"]["id"], "running").status_code == 404
    assert client.get(f"/api/devices/{MISSING}/state").status_code == 404