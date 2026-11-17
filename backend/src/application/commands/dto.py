"""What the command endpoints send and receive."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

CommandStatusName = Literal["success", "failed", "rejected"]


class CommandRequestDto(BaseModel):
    """Body of POST /api/commands."""

    command_type: str = Field(
        description="Which command to run: start_pump, stop_pump or set_light_level.",
        examples=["start_pump"],
    )
    device_id: UUID = Field(description="The actuator to send it to.")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description='Extra values for the command. set_light_level takes {"level": 0-100}.',
        examples=[{}, {"level": 1}],
    )


class CommandLogDto(BaseModel):
    """One row of command_log. What POST returns and GET lists."""

    id: UUID
    command_type: str
    device_id: UUID
    payload: dict[str, Any]
    status: CommandStatusName = Field(
        description="success, failed (a policy or the adapter said no) or rejected "
        "(not allowed in the actuator's current state)."
    )
    error_message: str | None = Field(
        default=None, examples=["Max run time exceeded"], description="Null on success."
    )
    created_at: datetime