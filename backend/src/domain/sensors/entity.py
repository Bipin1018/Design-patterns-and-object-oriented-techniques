from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(kw_only=True)
class Sensor:
    id: UUID | None = None
    device_type: str
    display_name: str
    default_config: dict[str, Any] = field(default_factory=dict)
    # Phase 5. The creator sets the interval, the repository writes it to the
    # column, and from there the column is what the sampler reads.
    sampling_interval_seconds: int = 300
    tracking_enabled: bool = True