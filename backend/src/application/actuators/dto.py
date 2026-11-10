"""What the actuator endpoints send and receive."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionDto(BaseModel):
    """One row of actuator_execution_log."""

    id: UUID
    device_id: UUID
    success: bool
    policy_applied: list[str] = Field(examples=[["maxRunTime", "logging"]])
    message: str | None = Field(default=None, examples=["Max run time exceeded"])
    created_at: datetime


class ApplyRequestDto(BaseModel):
    """Body of POST /api/actuators/{device_id}/apply."""

    command: str = Field(
        description="Not checked in this phase. Any name works unless a policy blocks it.",
        examples=["start_pump"],
    )
    payload: dict[str, Any] = Field(default_factory=dict)