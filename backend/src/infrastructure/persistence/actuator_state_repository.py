"""Reads and writes actuator_states. The only file that touches that table."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.infrastructure.persistence.models import ActuatorStateRow, DeviceRow

ACTUATOR_ROLE = "actuator"


@dataclass(frozen=True)
class StoredState:
    device_id: UUID
    state: str
    updated_at: datetime


class ActuatorStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def actuator_type(self, device_id: UUID) -> str | None:
        """The device_type of an actuator, or None. A sensor id also gives None."""
        return self._session.execute(
            select(DeviceRow.device_type).where(
                DeviceRow.id == device_id, DeviceRow.role == ACTUATOR_ROLE
            )
        ).scalar_one_or_none()

    def get(self, device_id: UUID, *, for_update: bool = False) -> StoredState | None:
        """One stored state. for_update locks the row until the next commit."""
        query = select(ActuatorStateRow).where(ActuatorStateRow.device_id == device_id)
        if for_update:
            query = query.with_for_update()
        row = self._session.execute(query).scalar_one_or_none()
        if row is None:
            return None
        return StoredState(device_id=row.device_id, state=row.state, updated_at=row.updated_at)

    def get_many(self, device_ids: Iterable[UUID]) -> dict[UUID, str]:
        """State per device id, in one query. Ids with no row are simply absent."""
        ids = list(device_ids)
        if not ids:
            return {}
        rows = self._session.execute(
            select(ActuatorStateRow.device_id, ActuatorStateRow.state).where(
                ActuatorStateRow.device_id.in_(ids)
            )
        ).all()
        return {device_id: state for device_id, state in rows}

    def save(self, device_id: UUID, state: str) -> StoredState:
        """Insert or update one row, then commit."""
        statement = (
            insert(ActuatorStateRow)
            .values(device_id=device_id, state=state)
            .on_conflict_do_update(
                index_elements=["device_id"],
                set_={"state": state, "updated_at": func.now()},
            )
            .returning(
                ActuatorStateRow.device_id,
                ActuatorStateRow.state,
                ActuatorStateRow.updated_at,
            )
        )
        saved_id, saved_state, updated_at = self._session.execute(statement).one()
        self._session.commit()
        return StoredState(device_id=saved_id, state=saved_state, updated_at=updated_at)

    def ensure(self, device_ids: Iterable[UUID], state: str) -> None:
        """Give each listed device a row if it has none. Existing rows are left alone."""
        ids = list(device_ids)
        if not ids:
            return
        self._session.execute(
            insert(ActuatorStateRow)
            .values([{"device_id": device_id, "state": state} for device_id in ids])
            .on_conflict_do_nothing(index_elements=["device_id"])
        )
        self._session.commit()