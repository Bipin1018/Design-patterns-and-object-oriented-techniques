"""Phase 11 end to end: events become alert rows, and GET /api/alerts reads them.

Needs the stack up: docker compose exec backend pytest tests -q

Fixtures delete what they create. Alerts are deleted first, because their
foreign keys are SET NULL: deleting only the device would leave the alert behind.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update

from src.application.readings.sampler import SimulationSampler
from src.application.readings.service import ReadingIngest
from src.domain.events.bus import EventBus
from src.domain.events.events import CommandFailed, ReadingCreated, ThresholdCrossed
from src.domain.sensors.reading import Reading
from src.infrastructure.db import SessionLocal
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.models import ActuatorStateRow, AlertRow, DeviceRow
from src.infrastructure.persistence.reading_repository import ReadingRepository
from src.interfaces.api.event_bus import build_event_bus, event_bus, get_event_bus
from src.main import app

client = TestClient(app)

ZONES = [
    {"name": "Bench 1", "moisture_threshold_low": 0.20, "moisture_threshold_high": 0.45},
    {"name": "Bench 2", "moisture_threshold_low": 0.30, "moisture_threshold_high": 0.60},
]
ALERT_FIELDS = {
    "id",
    "location_id",
    "zone_id",
    "device_id",
    "severity",
    "message",
    "event_type",
    "status",
    "created_at",
}


# -- Helpers --------------------------------------------------------------------


def alerts_for(device_id: str) -> list[AlertRow]:
    """Alert rows for one device, oldest first, read from the table."""
    with SessionLocal() as session:
        return list(
            session.execute(
                select(AlertRow)
                .where(AlertRow.device_id == UUID(device_id))
                .order_by(AlertRow.created_at)
            ).scalars()
        )


def get_alerts(**params: str) -> list[dict]:
    response = client.get("/api/alerts", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def create_moisture_sensor(name: str) -> str:
    response = client.post("/api/sensors", json={"type": "moisture", "display_name": name})
    assert response.status_code == 201
    return response.json()["id"]


def record(device_id: str, value: float, bus: EventBus = event_bus) -> None:
    """Save one moisture reading through ingest, like a translated MQTT message."""
    with SessionLocal() as session:
        ingest = ReadingIngest(DeviceRepository(session), ReadingRepository(session), bus)
        ingest.record(
            UUID(device_id),
            Reading(
                device_id=UUID(device_id),
                value=value,
                unit="vwc",
                source="mqtt",
                recorded_at=datetime.now(UTC),
            ),
        )


def set_tracking(device_id: str, enabled: bool) -> None:
    response = client.patch(
        f"/api/devices/{device_id}/sampling",
        json={"sampling_interval_seconds": 60, "tracking_enabled": enabled},
    )
    assert response.status_code == 200


def move(device_id: str, target: str) -> int:
    """POST the demo transition and return the status code."""
    return client.post(f"/api/devices/{device_id}/transition", json={"target": target}).status_code


def cleanup(device_ids: list[str]) -> None:
    ids = [UUID(device_id) for device_id in device_ids]
    with SessionLocal() as session:
        session.execute(delete(AlertRow).where(AlertRow.device_id.in_(ids)))
        session.execute(delete(DeviceRow).where(DeviceRow.id.in_(ids)))
        session.commit()


# -- Fixtures -------------------------------------------------------------------


@pytest.fixture
def site() -> Iterator[dict]:
    """Bench 1 (low 0.20) and Bench 2 (low 0.30), one sensor on Bench 1, one unassigned."""
    created = client.post(
        "/api/locations/config", json={"location_name": "Alert Site", "zones": ZONES}
    )
    assert created.status_code == 201
    body = created.json()
    zones = {zone["name"]: zone["id"] for zone in body["zones"]}

    placed = create_moisture_sensor("Bench 1 moisture")
    spare = create_moisture_sensor("Spare moisture")
    assert (
        client.patch(f"/api/devices/{placed}/zone", json={"zone_id": zones["Bench 1"]}).status_code
        == 200
    )

    yield {
        "location_id": body["location"]["id"],
        "bench_1": zones["Bench 1"],
        "bench_2": zones["Bench 2"],
        "placed": placed,
        "spare": spare,
    }

    cleanup([placed, spare])
    client.delete(f"/api/locations/{body['location']['id']}")


@pytest.fixture
def kit() -> Iterator[dict[str, dict]]:
    """A new simulation kit. Its pump has no zone, like the seeded pump."""
    response = client.post("/api/devices/provision?family=simulation")
    assert response.status_code == 201
    devices = response.json()

    yield {device["device_type"]: device for device in devices}

    cleanup([device["id"] for device in devices])


@pytest.fixture
def spy_bus() -> Iterator[list[ReadingCreated]]:
    """Give the routes a test bus that also records reading.created.

    The real bus has no unsubscribe, so we never add a spy to it.
    """
    bus = build_event_bus(SessionLocal)
    heard: list[ReadingCreated] = []
    bus.subscribe(ReadingCreated, heard.append)
    app.dependency_overrides[get_event_bus] = lambda: bus
    yield heard
    app.dependency_overrides.pop(get_event_bus, None)


# -- Step 2: the subscriber inserts on a published event ----------------------


def test_subscriber_inserts_on_published_event(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    bus = build_event_bus(SessionLocal)

    bus.publish(
        CommandFailed(
            device_id=UUID(pump),
            location_id=None,
            zone_id=None,
            command_type="stop_pump",
            message="Something broke",
        )
    )

    [alert] = alerts_for(pump)
    assert (alert.event_type, alert.severity, alert.status) == (
        "command.failed",
        "warning",
        "active",
    )
    assert alert.message == "Something broke"
    assert alert.acknowledged_at is None


def test_threshold_event_is_stored_as_a_warning(site: dict) -> None:
    bus = build_event_bus(SessionLocal)

    bus.publish(
        ThresholdCrossed(
            device_id=UUID(site["placed"]),
            location_id=UUID(site["location_id"]),
            zone_id=UUID(site["bench_1"]),
            moisture=0.1,
            threshold_low=0.2,
            recorded_at=datetime.now(UTC),
        )
    )

    [alert] = alerts_for(site["placed"])
    assert (alert.event_type, alert.severity, alert.message) == (
        "threshold.crossed",
        "warning",
        "Moisture below zone low",
    )


# -- Ingest publishes reading.created only while tracking is on ----------------


def test_manual_read_on_tracked_device_publishes(
    kit: dict[str, dict], spy_bus: list[ReadingCreated]
) -> None:
    sensor = kit["moisture_sensor"]["id"]

    response = client.post(f"/api/sensors/{sensor}/read")

    assert response.status_code == 201
    [event] = spy_bus
    assert event.device_id == UUID(sensor)
    assert event.value == pytest.approx(response.json()["value"])
    assert (event.unit, event.source) == ("vwc", "simulation")
    assert (event.location_id, event.zone_id) == (None, None)  # kit sensors are unplaced


def test_manual_read_with_tracking_off_stores_but_does_not_publish(
    kit: dict[str, dict], spy_bus: list[ReadingCreated]
) -> None:
    sensor = kit["moisture_sensor"]["id"]
    set_tracking(sensor, False)

    response = client.post(f"/api/sensors/{sensor}/read")

    assert response.status_code == 201  # still saved
    readings = client.get(f"/api/sensors/{sensor}/readings").json()
    assert len(readings) == 1
    assert spy_bus == []  # but not published


def test_sampler_on_tracked_device_publishes(kit: dict[str, dict]) -> None:
    sensor = kit["moisture_sensor"]["id"]
    bus = EventBus()
    heard: list[ReadingCreated] = []
    bus.subscribe(ReadingCreated, heard.append)

    with SessionLocal() as session:
        devices = DeviceRepository(session)
        readings = ReadingRepository(session)
        sampler = SimulationSampler(devices, readings, ReadingIngest(devices, readings, bus))
        sampler.run_once(datetime.now(UTC) + timedelta(days=1))

    assert UUID(sensor) in {event.device_id for event in heard}


def test_record_with_tracking_off_stores_but_does_not_publish(site: dict) -> None:
    """The MQTT path (ingest.record) follows the same rule."""
    set_tracking(site["placed"], False)

    record(site["placed"], 0.10)

    readings = client.get(f"/api/sensors/{site['placed']}/readings").json()
    assert len(readings) == 1
    assert alerts_for(site["placed"]) == []  # no event, so no threshold alert


# -- Step 4: the three alert rows -----------------------------------------------


def test_low_moisture_on_bench_1_creates_a_threshold_alert(site: dict) -> None:
    record(site["placed"], 0.10)  # Bench 1 low is 0.20

    [alert] = alerts_for(site["placed"])
    assert alert.event_type == "threshold.crossed"
    assert alert.severity == "warning"
    assert alert.message == "Moisture below zone low"
    assert str(alert.location_id) == site["location_id"]
    assert str(alert.zone_id) == site["bench_1"]

    bench_1 = get_alerts(zone_id=site["bench_1"])
    assert [row["id"] for row in bench_1] == [str(alert.id)]
    assert set(bench_1[0]) == ALERT_FIELDS  # acknowledged_at is not sent
    assert get_alerts(zone_id=site["bench_2"]) == []  # another zone does not see it
    assert [row["id"] for row in get_alerts(location_id=site["location_id"])] == [str(alert.id)]


def test_threshold_is_strictly_below(site: dict) -> None:
    record(site["placed"], 0.20)  # exactly on the line
    record(site["placed"], 0.35)  # comfortably above

    assert alerts_for(site["placed"]) == []


def test_unplaced_sensor_never_crosses_a_threshold(site: dict) -> None:
    record(site["spare"], 0.01)

    assert alerts_for(site["spare"]) == []


def test_failed_command_on_unassigned_pump_has_null_ids(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    assert client.post(
        "/api/commands", json={"command_type": "start_pump", "device_id": pump}
    ).json()["status"] == "success"
    with SessionLocal() as session:  # started 31 minutes ago
        session.execute(
            update(ActuatorStateRow)
            .where(ActuatorStateRow.device_id == UUID(pump))
            .values(updated_at=func.now() - timedelta(minutes=31))
        )
        session.commit()

    response = client.post("/api/commands", json={"command_type": "stop_pump", "device_id": pump})

    assert response.json()["status"] == "failed"
    [alert] = alerts_for(pump)
    assert alert.event_type == "command.failed"
    assert alert.severity == "warning"
    assert alert.message == "Max run time exceeded"
    assert alert.location_id is None
    assert alert.zone_id is None


def test_rejected_command_is_not_an_alert(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]

    response = client.post("/api/commands", json={"command_type": "stop_pump", "device_id": pump})

    assert response.status_code == 409
    assert alerts_for(pump) == []


def test_transition_to_error_creates_a_critical_alert(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]

    assert move(pump, "error") == 200

    [alert] = alerts_for(pump)
    assert alert.event_type == "state.changed"
    assert alert.severity == "critical"
    assert alert.message == "Actuator entered error"
    assert (alert.location_id, alert.zone_id) == (None, None)


def test_other_transitions_are_not_alerts(kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]

    assert move(pump, "running") == 200
    assert move(pump, "idle") == 200
    assert move(pump, "idle") == 409  # illegal: nothing saved, nothing published

    assert alerts_for(pump) == []


def test_placed_actuator_alert_copies_its_zone(site: dict, kit: dict[str, dict]) -> None:
    pump = kit["water_pump"]["id"]
    client.patch(f"/api/devices/{pump}/zone", json={"zone_id": site["bench_2"]})

    assert move(pump, "error") == 200

    [alert] = alerts_for(pump)
    assert str(alert.zone_id) == site["bench_2"]
    assert str(alert.location_id) == site["location_id"]


# -- GET /api/alerts parameters -------------------------------------------------


def test_status_filter_and_bad_values(site: dict) -> None:
    record(site["placed"], 0.10)
    zone = site["bench_1"]

    assert len(get_alerts(zone_id=zone)) == 1  # default is active
    assert len(get_alerts(zone_id=zone, status="active")) == 1
    assert len(get_alerts(zone_id=zone, status="all")) == 1
    assert get_alerts(zone_id=zone, status="resolved") == []

    assert client.get("/api/alerts", params={"status": "open"}).status_code == 400
    assert client.get("/api/alerts", params={"limit": 0}).status_code == 422
    assert client.get("/api/alerts", params={"limit": 201}).status_code == 422


def test_newest_first_since_and_limit(site: dict) -> None:
    record(site["placed"], 0.10)
    record(site["placed"], 0.05)
    first, second = alerts_for(site["placed"])  # oldest first
    zone = site["bench_1"]

    listed = get_alerts(zone_id=zone)
    assert [row["id"] for row in listed] == [str(second.id), str(first.id)]
    assert [row["id"] for row in get_alerts(zone_id=zone, limit="1")] == [str(second.id)]

    since = get_alerts(zone_id=zone, since=second.created_at.isoformat())
    assert [row["id"] for row in since] == [str(second.id)]  # at or after