"""Reads and writes command_log. The only file that touches that table."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.persistence.models import CommandLogRow


@dataclass(frozen=True)
class StoredCommand:
    id: UUID
    command_type: str
    device_id: UUID
    payload: dict[str, Any]
    status: str
    error_message: str | None
    created_at: datetime


class CommandLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        device_id: UUID,
        command_type: str,
        payload: dict[str, Any],
        *,
        status: str,
        error_message: str | None = None,
    ) -> StoredCommand:
        """Insert one row, commit straight away, and return it with its id and time.

        Committed here, like the execution log: a rejected or failed command
        must stay in the history whatever happens after this call.
        """
        row = CommandLogRow(
            device_id=device_id,
            command_type=command_type,
            payload=dict(payload),
            status=status,
            error_message=error_message,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)  # loads the id and created_at the database filled in
        return self._to_stored(row)

    def recent(self, limit: int) -> list[StoredCommand]:
        """Newest first."""
        query = (
            select(CommandLogRow)
            .order_by(CommandLogRow.created_at.desc(), CommandLogRow.id.desc())
            .limit(limit)
        )
        return [self._to_stored(row) for row in self._session.execute(query).scalars()]

    @staticmethod
    def _to_stored(row: CommandLogRow) -> StoredCommand:
        return StoredCommand(
            id=row.id,
            command_type=row.command_type,
            device_id=row.device_id,
            payload=dict(row.payload),
            status=row.status,
            error_message=row.error_message,
            created_at=row.created_at,
        )