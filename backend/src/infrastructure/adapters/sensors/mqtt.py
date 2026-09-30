"""The MQTT sensor adapter.

This one does not implement SensorPort, and that is the interesting part.

SensorPort promises "ask, and receive a reading". An MQTT device cannot be
asked. It publishes when it feels like it, and the backend receives whatever
arrives. So this class offers translate() and nothing else. Phase 12 will call
it from the device HTTP route or an optional subscriber, and hand the result to
ReadingIngest.record.

No broker is opened here, in Phase 5 or ever. Connecting is transport work and
belongs to Phase 12; translation is adapter work and belongs here. That split
is why the test for this file needs a dict and nothing more.
"""

from datetime import UTC, datetime
from typing import Any

from src.domain.devices.entity import Device
from src.domain.sensors.errors import AdapterError
from src.domain.sensors.reading import Reading

SOURCE = "mqtt"


class MqttSensorAdapter:
    def translate(self, device: Device, payload: dict[str, Any]) -> Reading:
        """Turn one inbound message body into a Reading.

        Expects {"value": 0.41, "unit": "vwc"} and optionally
        {"recorded_at": "2026-08-28T09:00:00Z"}. A message with no timestamp is
        stamped on arrival, which is the best the backend can do.
        """
        if device.id is None:
            raise AdapterError("Cannot record for an unsaved device: id is None.")

        try:
            value = float(payload["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError("MQTT payload has no numeric 'value'.") from exc

        unit = payload.get("unit")
        if not isinstance(unit, str) or not unit.strip():
            raise AdapterError("MQTT payload has no 'unit'.")

        return Reading(
            device_id=device.id,
            value=round(value, 4),
            unit=unit.strip(),
            source=SOURCE,
            recorded_at=_parse_timestamp(payload.get("recorded_at")),
        )


def _parse_timestamp(raw: Any) -> datetime:
    """Read an ISO-8601 string, or stamp now. Naive values are read as UTC."""
    if raw is None:
        return datetime.now(UTC)

    if not isinstance(raw, str):
        raise AdapterError("MQTT payload 'recorded_at' must be an ISO-8601 string.")

    try:
        # Python's parser wants +00:00; devices commonly send Z.
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdapterError(f"MQTT payload has an unreadable timestamp: {raw!r}.") from exc

    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)