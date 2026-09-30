"""API and sampler tests for readings.

These need the database, so run them with the stack up:
    docker compose exec backend pytest tests -q

Each test provisions its own kit and deletes it afterwards. Deleting a device
takes its readings with it through ON DELETE CASCADE, so nothing is left behind.

The sampler tests drive run_once with a fake clock rather than the app's
background task. Nothing sleeps.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.application.readings.sampler import SimulationSampler
from src.application.readings.service import ReadingIngest
from src.infrastructure.db import SessionLocal
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.models import DeviceRow
from src.infrastructure.persistence.reading_repository import ReadingRepository
from src.main import app

client = TestClient(app)

MISSING_ID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def kit() -> Iterator[list[dict]]:
    """One simulation kit, removed afterwards with its readings."""
    response = client.post("/api/devices/provision?family=simulation")
    assert response.status_code == 201
    devices = response.json()

    yield devices

    _delete_devices([device["id"] for device in devices])


@pytest.fixture
def edge_kit() -> Iterator[list[dict]]:
    """One edge kit. Its sensors are on the mqtt protocol."""
    response = client.post("/api/devices/provision?family=edge")
    assert response.status_code == 201
    devices = response.json()

    yield devices

    _delete_devices([device["id"] for device in devices])


def _delete_devices(device_ids: list[str]) -> None:
    """There is no delete endpoint, so clean up through the repository."""
    session = SessionLocal()
    try:
        for device_id in device_ids:
            row = session.get(DeviceRow, device_id)
            if row is not None:
                session.delete(row)
        session.commit()
    finally:
        session.close()


def sensor_of(devices: list[dict], device_type: str = "moisture_sensor") -> dict:
    return next(d for d in devices if d["device_type"] == device_type)


# -- the read endpoint ------------------------------------------------------


def test_read_inserts_sensor_reading(kit: list[dict]) -> None:
    """Each read appends. History is the point; overwriting would destroy it."""
    sensor = sensor_of(kit)

    first = client.post(f"/api/sensors/{sensor['id']}/read")
    second = client.post(f"/api/sensors/{sensor['id']}/read")

    assert first.status_code == 201
    assert second.status_code == 201

    body = first.json()
    assert body["device_id"] == sensor["id"]
    assert body["source"] == "simulation"
    assert body["unit"] == "vwc"
    assert 0.2 <= body["value"] <= 0.6

    stored = client.get(f"/api/sensors/{sensor['id']}/readings?limit=50").json()
    assert len(stored) == 2


def test_readings_come_back_newest_first(kit: list[dict]) -> None:
    sensor = sensor_of(kit)

    client.post(f"/api/sensors/{sensor['id']}/read")
    client.post(f"/api/sensors/{sensor['id']}/read")

    rows = client.get(f"/api/sensors/{sensor['id']}/readings?limit=50").json()
    timestamps = [row["recorded_at"] for row in rows]

    assert timestamps == sorted(timestamps, reverse=True)


def test_read_on_an_mqtt_device_is_rejected(edge_kit: list[dict]) -> None:
    """The selector refuses rather than inventing a value the device never sent."""
    sensor = sensor_of(edge_kit)

    response = client.post(f"/api/sensors/{sensor['id']}/read")

    assert response.status_code == 400
    assert "MQTT" in response.json()["detail"]


def test_read_on_a_missing_device_is_404() -> None:
    assert client.post(f"/api/sensors/{MISSING_ID}/read").status_code == 404


def test_readings_for_a_device_with_none_is_an_empty_list(kit: list[dict]) -> None:
    sensor = sensor_of(kit, "light_sensor")

    assert client.get(f"/api/sensors/{sensor['id']}/readings").json() == []


# -- the sampling endpoint --------------------------------------------------


def test_patch_sampling_round_trips(kit: list[dict]) -> None:
    sensor = sensor_of(kit)

    body = client.patch(
        f"/api/devices/{sensor['id']}/sampling",
        json={"sampling_interval_seconds": 30, "tracking_enabled": False},
    ).json()

    assert body["sampling_interval_seconds"] == 30
    assert body["tracking_enabled"] is False

    # And it is stored, not just echoed.
    listed = next(d for d in client.get("/api/sensors").json() if d["id"] == sensor["id"])
    assert listed["sampling_interval_seconds"] == 30
    assert listed["tracking_enabled"] is False


def test_patch_sampling_rejects_an_interval_below_five(kit: list[dict]) -> None:
    """Validated before the write, so the stored row is untouched."""
    sensor = sensor_of(kit)

    response = client.patch(
        f"/api/devices/{sensor['id']}/sampling",
        json={"sampling_interval_seconds": 2, "tracking_enabled": True},
    )

    assert response.status_code == 400
    assert "at least 5" in response.json()["detail"]

    listed = next(d for d in client.get("/api/sensors").json() if d["id"] == sensor["id"])
    assert listed["sampling_interval_seconds"] == 300


def test_patch_sampling_on_a_missing_device_is_404() -> None:
    response = client.patch(
        f"/api/devices/{MISSING_ID}/sampling",
        json={"sampling_interval_seconds": 30, "tracking_enabled": True},
    )

    assert response.status_code == 404


# -- the sampler ------------------------------------------------------------


def test_sampler_respects_interval_and_tracking(kit: list[dict]) -> None:
    """A fake clock, so nothing sleeps.

    Four ticks, one device: due with no rows, not due inside the interval, due
    again after it, and never once tracking is off.
    """
    sensor = sensor_of(kit)
    client.patch(
        f"/api/devices/{sensor['id']}/sampling",
        json={"sampling_interval_seconds": 60, "tracking_enabled": True},
    )

    session = SessionLocal()
    try:
        devices = DeviceRepository(session)
        readings = ReadingRepository(session)
        sampler = SimulationSampler(devices, readings, ReadingIngest(devices, readings))
        now = datetime.now(UTC)

        def count() -> int:
            return readings.count_for_device(sensor["id"])

        # No prior row counts as elapsed.
        sampler.run_once(now)
        assert count() == 1

        # Thirty seconds into a sixty second interval: not due.
        sampler.run_once(now + timedelta(seconds=30))
        assert count() == 1

        # Past the interval: due again.
        sampler.run_once(now + timedelta(seconds=90))
        assert count() == 2

        # Tracking off: never due, however long you wait.
        client.patch(
            f"/api/devices/{sensor['id']}/sampling",
            json={"sampling_interval_seconds": 60, "tracking_enabled": False},
        )
        session.expire_all()  # the PATCH went through a different session
        sampler.run_once(now + timedelta(hours=1))
        assert count() == 2
    finally:
        session.close()


def test_sampler_skips_mqtt_devices(edge_kit: list[dict]) -> None:
    """An MQTT device reports for itself. Sampling it would invent data."""
    sensor = sensor_of(edge_kit)

    session = SessionLocal()
    try:
        devices = DeviceRepository(session)
        readings = ReadingRepository(session)
        sampler = SimulationSampler(devices, readings, ReadingIngest(devices, readings))

        sampler.run_once(datetime.now(UTC) + timedelta(hours=1))

        assert readings.count_for_device(sensor["id"]) == 0
    finally:
        session.close()