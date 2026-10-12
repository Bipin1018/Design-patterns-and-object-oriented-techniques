"""What the automation API sends back."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StrategyOptionDto(BaseModel):
    """One entry in the dropdown, built from the strategy class itself."""

    key: str
    label: str
    description: str


class StrategyRuleDto(BaseModel):
    """A location's saved choice.

    persisted is false when no row exists yet and the default is in use, so the
    panel can say "not saved yet" rather than imply someone chose this.
    """

    location_id: UUID
    strategy_key: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None
    persisted: bool


class ZoneRecommendationDto(BaseModel):
    """What the strategy decided about one zone, and what it saw.

    The inputs travel with the decision. A recommendation nobody can check is
    not much use.
    """

    zone_id: UUID
    zone_name: str
    action: str
    reason: str
    score: float | None = None
    moisture: float | None = None
    light: float | None = None
    moisture_low: float
    moisture_high: float
    recorded_at: datetime | None = None
    source_device_id: UUID | None = None


class EvaluationDto(BaseModel):
    """One evaluation of one location.

    The four top-level fields are what the phase requires. zones carries the
    per-zone results underneath, because a location with three benches has
    three answers, not one.
    """

    location_id: UUID
    strategy_key: str
    action: str
    reason: str
    zones: list[ZoneRecommendationDto] = Field(default_factory=list)