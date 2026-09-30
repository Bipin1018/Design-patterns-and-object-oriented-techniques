"""Choosing an adapter for a device.

The one place in the codebase that names concrete adapter classes. Everything
above it depends on SensorPort, which is what lets a new protocol arrive
without touching a use case. Same idea as get_creator in Phase 2 and
get_family_factory in Phase 3: a lookup, and a ValueError on an unknown key.

The rule, in order:

1. default_config.vendor_stub is true  -> the vendor stub
2. default_config.protocol is "simulation" -> the simulation adapter
3. default_config.protocol is "mqtt"       -> no adapter; readings arrive, they
                                              are not requested

The vendor stub gets its own boolean rather than a protocol value on purpose.
"vendor" is not a protocol, it is a supplier, so a device could one day be both
vendor-made and MQTT-connected. Keeping them on separate keys means the two can
never collide. No family provisions vendor devices; the flag is set by hand on
a device, and the translation is exercised by its unit test.

Rows with no protocol at all are read as simulation. After the Phase 5
migration there should be none, but a default beats a crash.
"""

from src.domain.devices.entity import Device
from src.domain.sensors.errors import AdapterError
from src.domain.sensors.ports import SensorPort
from src.infrastructure.adapters.sensors.mqtt import MqttSensorAdapter
from src.infrastructure.adapters.sensors.simulation import SimulationSensorAdapter
from src.infrastructure.adapters.sensors.vendor_stub import VendorStubSensorAdapter

PROTOCOL_SIMULATION = "simulation"
PROTOCOL_MQTT = "mqtt"
VENDOR_STUB_FLAG = "vendor_stub"

# Built once and shared. The adapters hold no per-device state, so one instance
# serves every device, exactly like the Phase 2 creator registry.
_SIMULATION = SimulationSensorAdapter()
_VENDOR_STUB = VendorStubSensorAdapter()
_MQTT = MqttSensorAdapter()


def protocol_of(device: Device) -> str:
    """The device's protocol, defaulting to simulation when it has none."""
    protocol = device.default_config.get("protocol")
    return protocol if isinstance(protocol, str) and protocol else PROTOCOL_SIMULATION


def get_sensor_port(device: Device) -> SensorPort:
    """The adapter that can read this device.

    Raises AdapterError for an MQTT device, because asking one for a reading is
    not a thing you can do. The router turns that into a 400 with this message.
    """
    if device.role != "sensor":
        raise AdapterError(f"Device {device.id} is an actuator, not a sensor.")

    if device.default_config.get(VENDOR_STUB_FLAG) is True:
        return _VENDOR_STUB

    protocol = protocol_of(device)

    if protocol == PROTOCOL_SIMULATION:
        return _SIMULATION

    if protocol == PROTOCOL_MQTT:
        raise AdapterError(
            f"Device {device.id} delivers readings over MQTT, so it cannot be "
            f"read on demand. Its readings arrive from the device."
        )

    raise AdapterError(
        f"No sensor adapter for protocol '{protocol}'. "
        f"Known protocols: {PROTOCOL_MQTT}, {PROTOCOL_SIMULATION}."
    )


def get_mqtt_adapter() -> MqttSensorAdapter:
    """The MQTT translator. Phase 12's ingest route calls this."""
    return _MQTT