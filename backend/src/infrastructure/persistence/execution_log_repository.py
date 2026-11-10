"""Reads and writes actuator_execution_log. The only file that touches that table."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.actuators.ports import ExecutionLogPort
from src.infrastructure.persistence.models import ActuatorExecutionLogRow


@dataclass(frozen=True)
class StoredExecution:
    id: UUID
    device_id: UUID
    success: bool
    policy_applied: list[str]
    message: str | None
    created_at: datetime


class ExecutionLogRepository(ExecutionLogPort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        device_id: UUID,
        *,
        success: bool,
        policy_applied: list[str],
        message: str | None,
    ) -> None:
        """Insert one row and commit straight away.

        Committed here, not by the caller, because a refused command raises
        right after this. The row must already be saved by then, or the
        failure it describes would vanish with the rollback.
        """
        self._session.add(
            ActuatorExecutionLogRow(
                device_id=device_id,
                success=success,
                policy_applied=list(policy_applied),
                message=message,
            )
        )
        self._session.commit()

    def recent(self, limit: int, device_id: UUID | None = None) -> list[StoredExecution]:
        """Newest first. Optionally for one device only."""
        query = select(ActuatorExecutionLogRow)
        if device_id is not None:
            query = query.where(ActuatorExecutionLogRow.device_id == device_id)
        query = query.order_by(
            ActuatorExecutionLogRow.created_at.desc(), ActuatorExecutionLogRow.id.desc()
        ).limit(limit)
        return [self._to_stored(row) for row in self._session.execute(query).scalars()]

    @staticmethod
    def _to_stored(row: ActuatorExecutionLogRow) -> StoredExecution:
        return StoredExecution(
            id=row.id,
            device_id=row.device_id,
            success=row.success,
            policy_applied=list(row.policy_applied),
            message=row.message,
            created_at=row.created_at,
        )