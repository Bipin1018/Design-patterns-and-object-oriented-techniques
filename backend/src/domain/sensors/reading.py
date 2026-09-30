"""The normalized reading.

Every adapter, whatever shape its source speaks, produces one of these. That is
the whole point of the Adapter pattern here: the application layer above never
learns that a vendor sends permille and an epoch in milliseconds, because the
adapter has already turned it into this.

Frozen for the same reason Device is frozen. A reading is a record of what a
sensor said at a moment. Nothing downstream should quietly rewrite it.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Reading:
    device_id: UUID
    value: float
    unit: str  # "vwc" or "lux"
    # Where the number came from: "simulation", "vendor" or "mqtt".
    # It is the adapter's signature, which is why the API shows it.
    source: str
    recorded_at: datetime  # timezone-aware, always UTC