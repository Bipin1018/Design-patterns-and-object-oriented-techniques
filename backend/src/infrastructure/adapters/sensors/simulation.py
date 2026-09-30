"""The simulation sensor adapter.

Generates a value in software. No hardware, no network, no file. This is what
the simulation family has meant since Phase 3: fake devices that behave like
real ones from the outside.

The ranges are per device type, and so is the unit. The adapter does not read
the unit out of default_config, for the same reason the Phase 2 creator owns it
rather than the client: a light sensor reporting "vwc" would be nonsense, and
nothing should be able to write it.
"""

import random
from datetime import UTC, datetime

from src.domain.devices.entity import Device
from src.domain.sensors.errors import AdapterError
from src.domain.sensors.ports import SensorPort
from src.domain.sensors.reading import Reading

SOURCE = "simulation"

# device_type -> (unit, low, high, decimal places)
RANGES: dict[str, tuple[str, float, float, int]] = {
    "moisture_sensor": ("vwc", 0.2, 0.6, 3),
    "light_sensor": ("lux", 200.0, 2000.0, 0),
}


class SimulationSensorAdapter(SensorPort):
    def read(self, device: Device) -> Reading:
        """Invent one plausible reading for this device type."""
        if device.id is None:
            raise AdapterError("Cannot read an unsaved device: id is None.")

        try:
            unit, low, high, places = RANGES[device.device_type]
        except KeyError:
            known = ", ".join(sorted(RANGES))
            raise AdapterError(
                f"The simulation adapter cannot read '{device.device_type}'. "
                f"It knows: {known}."
            ) from None

        return Reading(
            device_id=device.id,
            value=round(random.uniform(low, high), places),
            unit=unit,
            source=SOURCE,
            # UTC, always. The column is timestamptz, and a naive datetime here
            # would be stored as if it were local time.
            recorded_at=datetime.now(UTC),
        )