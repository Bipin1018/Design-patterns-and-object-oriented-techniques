"""Health endpoint: reports whether the API is up and whether it reaches Postgres."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.infrastructure.db import check_database

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Health payload consumed by the dashboard badge."""

    status: Literal["ok", "degraded"] = Field(
        description="'ok' when every dependency answers, 'degraded' when one does not."
    )
    db: Literal["ok", "fail"] = Field(description="Result of a SELECT 1 against PostgreSQL.")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description="Reports API availability and PostgreSQL connectivity.",
)
def read_health() -> HealthResponse:
    database_reachable = check_database()
    return HealthResponse(
        status="ok" if database_reachable else "degraded",
        db="ok" if database_reachable else "fail",
    )
