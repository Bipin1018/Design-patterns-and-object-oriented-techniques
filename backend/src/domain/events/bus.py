"""The event bus. Publishers send events here, subscribers receive them.

Everything runs in the same process, one handler after another.
There is no unsubscribe: handlers are set up once when the app starts.
"""

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: defaultdict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Handler) -> None:
        """Call this handler whenever an event of this type is published."""
        self._handlers[event_type].append(handler)

    def publish(self, event: object) -> None:
        """Call each handler for this event, in the order they subscribed.

        If a handler fails, log it and carry on. The publisher's work is
        already saved, so one broken handler shouldn't undo that.
        """
        for handler in list(self._handlers.get(type(event), ())):
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Handler %r failed on %s", handler, getattr(event, "event_type", event)
                )

    def handler_count(self, event_type: type) -> int:
        """How many handlers listen to this type. Used in tests."""
        return len(self._handlers.get(event_type, ()))