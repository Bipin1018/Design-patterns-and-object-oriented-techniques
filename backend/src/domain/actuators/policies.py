"""Actuator policies: their names, the max-run-time rule, and the refusal error.

Plain Python, like state.py. No SQLAlchemy, no FastAPI, so the rule can be
tested with nothing but a clock value.

The names are what lands in actuator_execution_log.policy_applied. They are
written exactly as the requirements spell them, camelCase included.
"""

from datetime import datetime, timedelta

from src.domain.actuators.state import RUNNING

POLICY_LOGGING = "logging"
POLICY_MAX_RUN_TIME = "maxRunTime"

# How long an actuator may stay running before further commands are refused.
MAX_RUN_TIME = timedelta(minutes=30)
MAX_RUN_TIME_EXCEEDED = "Max run time exceeded"


class ActuatorPolicyError(Exception):
    """A policy refused the command. The inner adapter was never called.

    Not a ValueError on purpose: the routers turn ValueError into 400, and a
    refused command is a 409. It carries the policy name so the logging
    decorator can record who said no without knowing any decorator by class.
    """

    def __init__(self, policy: str, message: str) -> None:
        super().__init__(message)
        self.policy = policy
        self.message = message


def max_run_time_exceeded(state: str, updated_at: datetime, now: datetime) -> bool:
    """True when the actuator is running and has been for at least MAX_RUN_TIME.

    updated_at is when actuator_states last changed. While the state is
    running, that is the moment it started running.
    """
    return state == RUNNING and now - updated_at >= MAX_RUN_TIME
