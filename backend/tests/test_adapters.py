"""Unit tests for the sensor adapters.

No database, no HTTP, no broker. Adapters translate, and translation is a pure
function of its input, so these run on their own in milliseconds.

The vendor and MQTT tests are the heart of the Adapter pattern: two completely
different payload shapes, one Reading out of both.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.domain.devices.entity import Device
from src.domain.sensors.errors import AdapterError
from src.infrastructure.adapters.actuators.simulation import SimulationActuatorAdapter
from src.infrastructure.adapters.sensors.mqtt import MqttSensorAdapter
from src.infrastructure.adapters.sensors.selector import get_sensor_port
from src.infrastructure.adapters.sensors.simulation import SimulationSensorAdapter
from src.infrastructure.adapters.sensors.vendor_stub import VendorStubSensorAdapter


def make_device(
    device_type: str = "moisture_sensor",
    protocol: str = "simulation",
    **extra: object,
) -> Device:
    """A saved device, built in memory. No repository involved."""
    return Device(
        id=uuid4(),
        device_type=device_type,
        role="sensor",
        device_family="simulation",
        display_name="Test sensor",
        default_config={"protocol": protocol, **extra},
    )


# -- simulation adapter -----------------------------------------------------


def test_simulation_adapter_value_in_range() -> None:
    """Twenty reads, because one passing proves nothing about a random range."""
    adapter = SimulationSensorAdapter()
    moisture = make_device("moisture_sensor")
    light = make_device("light_sensor")

    for _ in range(20):
        wet = adapter.read(moisture)
        assert 0.2 <= wet.value <= 0.6
        assert wet.unit == "vwc"
        assert wet.source == "simulation"

        bright = adapter.read(light)
        assert 200 <= bright.value <= 2000
        assert bright.unit == "lux"


def test_simulation_adapter_stamps_an_aware_utc_time() -> None:
    """A naive datetime would be stored as if it were local time."""
    reading = SimulationSensorAdapter().read(make_device())

    assert reading.recorded_at.tzinfo is not None
    assert reading.recorded_at.utcoffset() == UTC.utcoffset(None)


def test_simulation_adapter_rejects_an_unknown_device_type() -> None:
    with pytest.raises(AdapterError, match="cannot read 'water_pump'"):
        SimulationSensorAdapter().read(make_device("water_pump"))


# -- vendor adapter ---------------------------------------------------------


def test_vendor_adapter_normalizes_raw_payload() -> None:
    """The point of Adapter: their shape in, our shape out.

    412 permille is our 0.412 vwc, and an epoch in milliseconds is our aware
    UTC datetime. Nothing above this adapter ever learns those words.
    """
    device = make_device()
    raw = {
        "sensorId": "SMS-0042",
        "measurement": {"raw": 412, "scale": "permille"},
        "capturedAtEpochMs": 1756370400000,
    }

    reading = VendorStubSensorAdapter().translate(device, raw)

    assert reading.value == 0.412
    assert reading.unit == "vwc"
    assert reading.source == "vendor"
    assert reading.device_id == device.id
    assert reading.recorded_at == datetime(2025, 8, 28, 8, 40, tzinfo=UTC)


def test_vendor_and_simulation_differ_on_the_same_device() -> None:
    """Two adapters, one device, two sources. That is the pattern working."""
    device = make_device()

    assert SimulationSensorAdapter().read(device).source == "simulation"
    assert VendorStubSensorAdapter().read(device).source == "vendor"


def test_vendor_adapter_rejects_a_malformed_payload() -> None:
    device = make_device()

    with pytest.raises(AdapterError, match="unknown scale"):
        VendorStubSensorAdapter().translate(
            device,
            {"measurement": {"raw": 1, "scale": "furlongs"}, "capturedAtEpochMs": 0},
        )

    with pytest.raises(AdapterError, match="no 'measurement'"):
        VendorStubSensorAdapter().translate(device, {"capturedAtEpochMs": 0})


# -- mqtt adapter -----------------------------------------------------------


def test_mqtt_adapter_translates_payload() -> None:
    """A dict is the whole input. No broker, no socket, no Phase 12."""
    device = make_device(protocol="mqtt")

    reading = MqttSensorAdapter().translate(device, {"value": 0.41, "unit": "vwc"})

    assert reading.value == 0.41
    assert reading.unit == "vwc"
    assert reading.source == "mqtt"
    assert reading.device_id == device.id
    # No timestamp in the payload, so the adapter stamped arrival.
    assert reading.recorded_at.tzinfo is not None


def test_mqtt_adapter_reads_a_z_suffixed_timestamp() -> None:
    """Devices send Z; Python's parser wants +00:00. The adapter bridges that."""
    device = make_device(protocol="mqtt")

    reading = MqttSensorAdapter().translate(
        device,
        {"value": 0.41, "unit": "vwc", "recorded_at": "2026-08-28T09:00:00Z"},
    )

    assert reading.recorded_at == datetime(2026, 8, 28, 9, 0, tzinfo=UTC)


def test_mqtt_adapter_rejects_a_payload_with_no_value() -> None:
    with pytest.raises(AdapterError, match="no numeric 'value'"):
        MqttSensorAdapter().translate(make_device(protocol="mqtt"), {"unit": "vwc"})


# -- selector ---------------------------------------------------------------


def test_selector_picks_by_protocol_and_vendor_flag() -> None:
    assert isinstance(get_sensor_port(make_device()), SimulationSensorAdapter)
    assert isinstance(
        get_sensor_port(make_device(vendor_stub=True)),
        VendorStubSensorAdapter,
    )


def test_selector_refuses_to_read_an_mqtt_device() -> None:
    """Asking an MQTT device for a value is not a thing you can do."""
    with pytest.raises(AdapterError, match="delivers readings over MQTT"):
        get_sensor_port(make_device(protocol="mqtt"))


# -- actuator port ----------------------------------------------------------


def test_simulation_actuator_records_the_command() -> None:
    """Phase 9 wraps this class, so it has to exist and stay dull."""
    adapter = SimulationActuatorAdapter()
    device_id = uuid4()

    adapter.apply(device_id, "start", {"seconds": 30})

    assert len(adapter.applied) == 1
    assert adapter.applied[0].device_id == device_id
    assert adapter.applied[0].command == "start"
    assert adapter.applied[0].payload == {"seconds": 30}