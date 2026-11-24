"""The two subscribers. Each listens on the bus and reacts to events.

Publishers never call these directly. Each handler opens its own short
database session, because the bus lives longer than any single request.
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from src.application.alerts.dto import CRITICAL, WARNING
from src.domain.actuators.state import ERROR
from src.domain.events.bus import EventBus
from src.domain.events.events import (
    ActuatorStateChanged,
    AlertCreated,
    CommandFailed,
    ReadingCreated,
    ThresholdCrossed,
)
from src.infrastructure.persistence.alert_repository import AlertRepository
from src.infrastructure.persistence.location_repository import LocationRepository

SessionFactory = Callable[[], Session]

MOISTURE_UNIT = "vwc"

MOISTURE_BELOW_LOW = "Moisture below zone low"
ACTUATOR_ENTERED_ERROR = "Actuator entered error"


class MoistureThresholdSubscriber:
    """Checks each reading. If moisture is too low, publishes ThresholdCrossed."""

    def __init__(self, bus: EventBus, session_factory: SessionFactory) -> None:
        self._bus = bus
        self._session_factory = session_factory

    def on_reading(self, event: ReadingCreated) -> None:
        # Only moisture readings from a sensor that is in a zone.
        if event.unit != MOISTURE_UNIT or event.zone_id is None:
            return

        with self._session_factory() as session:
            zone = LocationRepository(session).get_zone_by_id(event.zone_id)
            if zone is None:  # zone was deleted meanwhile
                return
            low = float(zone.moisture_threshold_low)  # the database gives a Decimal

        if event.value < low:  # strictly below, so exactly at the threshold is fine
            self._bus.publish(
                ThresholdCrossed(
                    device_id=event.device_id,
                    location_id=event.location_id,
                    zone_id=event.zone_id,
                    moisture=event.value,
                    threshold_low=low,
                    recorded_at=event.recorded_at,
                )
            )


class AlertPersistenceSubscriber:
    """Saves an alert row for the events that need one. The only writer of alerts."""

    def __init__(self, bus: EventBus, session_factory: SessionFactory) -> None:
        self._bus = bus
        self._session_factory = session_factory

    def on_threshold(self, event: ThresholdCrossed) -> None:
        self._store(event, event.event_type, WARNING, MOISTURE_BELOW_LOW)

    def on_command(self, event: CommandFailed) -> None:
        self._store(event, event.event_type, WARNING, event.message)

    def on_state(self, event: ActuatorStateChanged) -> None:
        # Every state change arrives here, but only error gets an alert.
        if event.state != ERROR:
            return
        self._store(event, event.event_type, CRITICAL, ACTUATOR_ENTERED_ERROR)

    def _store(
        self,
        event: ThresholdCrossed | CommandFailed | ActuatorStateChanged,
        event_type: str,
        severity: str,
        message: str,
    ) -> None:
        with self._session_factory() as session:
            stored = AlertRepository(session).add(
                device_id=event.device_id,
                location_id=event.location_id,
                zone_id=event.zone_id,
                severity=severity,
                message=message,
                event_type=event_type,
            )

        # Nobody listens to this yet. Phase 12 will.
        self._bus.publish(
            AlertCreated(
                alert_id=stored.id,
                device_id=stored.device_id,
                location_id=stored.location_id,
                zone_id=stored.zone_id,
                severity=stored.severity,
                message=stored.message,
                alert_event_type=stored.event_type,
                status=stored.status,
                created_at=stored.created_at,
            )
        )