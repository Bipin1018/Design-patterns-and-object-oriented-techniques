"""Logging decorator. Outermost layer: writes one row for every attempt."""

import logging
from typing import Any
from uuid import UUID

from src.domain.actuators.policies import POLICY_LOGGING, ActuatorPolicyError
from src.domain.actuators.ports import ActuatorPort, ExecutionLogPort

logger = logging.getLogger(__name__)


class LoggingActuatorDecorator(ActuatorPort):
    def __init__(self, inner: ActuatorPort, log: ExecutionLogPort) -> None:
        self._inner = inner
        self._log = log

    def apply(self, device_id: UUID, command: str, payload: dict[str, Any]) -> None:
        try:
            self._inner.apply(device_id, command, payload)
        except ActuatorPolicyError as exc:
            # A policy said no.
            self._write(device_id, command, False, [exc.policy, POLICY_LOGGING], exc.message)
            raise
        except Exception as exc:
            # The adapter failed.
            message = str(exc) or type(exc).__name__
            self._write(device_id, command, False, [POLICY_LOGGING], message)
            raise
        # It worked.
        self._write(device_id, command, True, [POLICY_LOGGING], None)

    def _write(
        self,
        device_id: UUID,
        command: str,
        success: bool,
        policies: list[str],
        message: str | None,
    ) -> None:
        self._log.record(device_id, success=success, policy_applied=policies, message=message)
        logger.info(
            "Actuator %s command %r: success=%s policies=%s message=%s",
            device_id,
            command,
            success,
            policies,
            message,
        )