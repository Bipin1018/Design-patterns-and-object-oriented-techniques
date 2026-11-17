"""What the actuator endpoints send and receive."""

from datetime import datetime
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