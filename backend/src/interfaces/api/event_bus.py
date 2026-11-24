"""Creates the one event bus for the app and connects the subscribers.

Routes get this bus through get_event_bus. The sampler in main.py uses
event_bus directly. Phase 12 will add the WebSocket here.
"""

from src.application.alerts.subscribers import (
    AlertPersistenceSubscriber,
    MoistureThresholdSubscriber,
    SessionFactory,
)
from src.domain.events.bus import EventBus
from src.domain.events.events import (
    ActuatorStateChanged,
    CommandFailed,
    ReadingCreated,
    ThresholdCrossed,
)
from src.infrastructure.db import SessionLocal


def build_event_bus(session_factory: SessionFactory = SessionLocal) -> EventBus:
    bus = EventBus()

    threshold = MoistureThresholdSubscriber(bus, session_factory)
    alerts = AlertPersistenceSubscriber(bus, session_factory)

    bus.subscribe(ReadingCreated, threshold.on_reading)
    bus.subscribe(ThresholdCrossed, alerts.on_threshold)
    bus.subscribe(CommandFailed, alerts.on_command)
    bus.subscribe(ActuatorStateChanged, alerts.on_state)

    return bus


# One bus for the whole app.
event_bus = build_event_bus()


def get_event_bus() -> EventBus:
    """FastAPI dependency. Always returns the same bus."""
    return event_bus