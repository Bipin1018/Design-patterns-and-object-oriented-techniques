"""The vendor stub sensor adapter.

The clearest example of Adapter in this project. A supplier's device does not
speak our language, and we cannot make it. So we translate.

Their payload looks like this:

    {"sensorId": "SMS-0042",
     "measurement": {"raw": 412, "scale": "permille"},
     "capturedAtEpochMs": 1756370400000}

Ours needs value, unit, source and an aware datetime. translate() is the whole
adapter: 412 permille becomes 0.412 vwc, and the epoch becomes a UTC datetime.

Translate only. This adapter never decides whether 0.412 is dry enough to
water — that is a Phase 6 Strategy question, and putting it here would mean
every future vendor had to reimplement the policy.

read() exists so the class satisfies SensorPort. _fetch_raw stands in for the
supplier's SDK, which this course does not have. Tests call translate directly
with a fixed payload, so no network is involved anywhere.
"""

import random
from datetime import UTC, datetime
from typing import Any

from src.domain.devices.entity import Device
from src.domain.sensors.errors import AdapterError
from src.domain.sensors.ports import SensorPort
from src.domain.sensors.reading import Reading

SOURCE = "vendor"

# Their scale name -> (our unit, what to multiply their number by)
SCALES: dict[str, tuple[str, float]] = {
    "permille": ("vwc", 0.001),  # 412 permille -> 0.412 vwc
    "lux": ("lux", 1.0),  # already our unit
}


class VendorStubSensorAdapter(SensorPort):
    def read(self, device: Device) -> Reading:
        """Fetch a raw payload and translate it."""
        return self.translate(device, self._fetch_raw(device))

    def translate(self, device: Device, raw: dict[str, Any]) -> Reading:
        """Turn one vendor payload into a Reading.

        Every failure here is an AdapterError, which the router turns into a
        400. A malformed payload is a bad request, not a crash.
        """
        if device.id is None:
            raise AdapterError("Cannot read an unsaved device: id is None.")

        measurement = raw.get("measurement")
        if not isinstance(measurement, dict):
            raise AdapterError("Vendor payload has no 'measurement' object.")

        scale = measurement.get("scale")
        try:
            unit, factor = SCALES[scale]
        except KeyError:
            known = ", ".join(sorted(SCALES))
            raise AdapterError(
                f"Vendor payload uses unknown scale '{scale}'. Known: {known}."
            ) from None

        try:
            value = float(measurement["raw"]) * factor
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError("Vendor payload has no numeric 'raw' value.") from exc

        try:
            captured_ms = int(raw["capturedAtEpochMs"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError("Vendor payload has no 'capturedAtEpochMs'.") from exc

        return Reading(
            device_id=device.id,
            value=round(value, 4),
            unit=unit,
            source=SOURCE,
            recorded_at=datetime.fromtimestamp(captured_ms / 1000, tz=UTC),
        )

    @staticmethod
    def _fetch_raw(device: Device) -> dict[str, Any]:
        """Stand-in for the supplier's SDK, which this course does not have.

        Everything above this line is real translation work. Only this method
        is invented, and only because there is no supplier to call.
        """
        if device.device_type == "light_sensor":
            measurement = {"raw": random.randint(200, 2000), "scale": "lux"}
        else:
            measurement = {"raw": random.randint(200, 600), "scale": "permille"}

        return {
            "sensorId": f"VND-{str(device.id)[:8]}",
            "measurement": measurement,
            "capturedAtEpochMs": int(datetime.now(UTC).timestamp() * 1000),
        }