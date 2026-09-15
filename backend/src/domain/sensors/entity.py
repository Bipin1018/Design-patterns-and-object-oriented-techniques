
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(kw_only=True)
class Sensor:
    id: UUID | None = None  # None until the repository saves it
    device_type: str
    display_name: str
    default_config: dict[str, Any] = field(default_factory=dict)