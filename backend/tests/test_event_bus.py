"""Observer tests that need no database: the bus, the ingest publish rule
(with fake repositories), and the rule that publishers don't import alerts."""

import ast
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from src.application.readings.service import ReadingIngest
from src.domain.devices.entity import Device
from src.domain.events.bus import EventBus
from src.domain.events.events import ReadingCreated, ThresholdCrossed
from src.domain.sensors.reading import Reading

SRC = Path(__file__).resolve().parents[1] / "src"

# -- The bus ------------------------------------------------------------------


def _reading_event(**overrides: object) -> ReadingCreated:
    values: dict = {
        "device_id": uuid4(),
        "location_id": None,
        "zone_id": None,
        "value": 0.3,
        "unit": "vwc",
        "source": "simulation",
        "recorded_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ReadingCreated(**values)


def test_handlers_run_in_subscription_order() -> None:
    bus = EventBus()
    calls: list[str] = []
    bus.subscribe(ReadingCreated, lambda event: calls.append("first"))
    bus.subscribe(ReadingCreated, lambda event: calls.append("second"))
    bus.subscribe(ReadingCreated, lambda event: calls.append("third"))

    bus.publish(_reading_event())

    assert calls == ["first", "second", "third"]


def test_only_handlers_for_that_class_are_called() -> None:
    bus = EventBus()
    heard: list[object] = []
    bus.subscribe(ThresholdCrossed, heard.append)

    bus.publish(_reading_event())

    assert heard == []


def test_a_failing_handler_does_not_stop_the_others() -> None:
    bus = EventBus()
    heard: list[object] = []

    def broken(event: object) -> None:
        raise RuntimeError("boom")

    bus.subscribe(ReadingCreated, broken)
    bus.subscribe(ReadingCreated, heard.append)
    event = _reading_event()

    bus.publish(event)  # does not raise

    assert heard == [event]


def test_the_bus_has_no_unsubscribe() -> None:
    assert not hasattr(EventBus(), "unsubscribe")


def test_event_type_is_the_wire_name() -> None:
    assert ReadingCreated.event_type == "reading.created"
    assert ThresholdCrossed.event_type == "threshold.crossed"


# -- Ingest publishes, with fakes ----------------------------------------------


class FakeDevices:
    """Stands in for DeviceRepository."""

    def __init__(self, device: Device) -> None:
        self._device = device

    def get_device(self, device_id: UUID) -> Device | None:
        return self._device if device_id == self._device.id else None


class FakeReadings:
    """Stands in for ReadingRepository. Keeps rows in a list."""

    def __init__(self) -> None:
        self.rows: list[Reading] = []

    def insert(self, reading: Reading) -> Reading:
        self.rows.append(reading)
        return reading


def _device(*, tracking: bool, placed: bool) -> Device:
    return Device(
        id=uuid4(),
        device_type="moisture_sensor",
        role="sensor",
        device_family="edge",
        display_name="Bench moisture",
        default_config={"protocol": "mqtt"},
        zone_id=uuid4() if placed else None,
        location_id=uuid4() if placed else None,
        tracking_enabled=tracking,
    )


def _ingest(device: Device) -> tuple[ReadingIngest, FakeReadings, list[ReadingCreated]]:
    bus = EventBus()
    heard: list[ReadingCreated] = []
    bus.subscribe(ReadingCreated, heard.append)
    readings = FakeReadings()
    return ReadingIngest(FakeDevices(device), readings, bus), readings, heard  # type: ignore[arg-type]


def _reading(device: Device, value: float = 0.1) -> Reading:
    assert device.id is not None
    return Reading(
        device_id=device.id, value=value, unit="vwc", source="mqtt", recorded_at=datetime.now(UTC)
    )


def test_tracked_ingest_publishes_reading_created_with_placement() -> None:
    device = _device(tracking=True, placed=True)
    ingest, readings, heard = _ingest(device)

    ingest.record(device.id, _reading(device))  # type: ignore[arg-type]

    assert len(readings.rows) == 1
    [event] = heard
    assert event.device_id == device.id
    assert (event.location_id, event.zone_id) == (device.location_id, device.zone_id)
    assert (event.value, event.unit, event.source) == (0.1, "vwc", "mqtt")


def test_untracked_ingest_stores_but_does_not_publish() -> None:
    device = _device(tracking=False, placed=True)
    ingest, readings, heard = _ingest(device)

    ingest.record(device.id, _reading(device))  # type: ignore[arg-type]

    assert len(readings.rows) == 1  # saved
    assert heard == []  # but not published


def test_unplaced_device_publishes_null_ids() -> None:
    device = _device(tracking=True, placed=False)
    ingest, _, heard = _ingest(device)

    ingest.record(device.id, _reading(device))  # type: ignore[arg-type]

    [event] = heard
    assert event.location_id is None
    assert event.zone_id is None


# -- Publishers do not know about alerts ---------------------------------------


PUBLISHERS = [
    "application/readings/service.py",  # ReadingIngest
    "application/readings/sampler.py",  # uses ingest, never publishes itself
    "application/commands/service.py",  # CommandService
    "application/devices/state_service.py",  # ActuatorStateService (transition service)
]


def _imported_names(path: Path) -> set[str]:
    """Every module and name a file imports, read from its source."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


@pytest.mark.parametrize("relative", PUBLISHERS)
def test_publishers_do_not_import_the_alerts_side(relative: str) -> None:
    imported = _imported_names(SRC / relative)

    assert "AlertRepository" not in imported
    assert "src.infrastructure.persistence.alert_repository" not in imported
    assert not any(name.startswith("src.application.alerts") for name in imported)
    assert not any(name.startswith(("fastapi", "src.interfaces")) for name in imported)