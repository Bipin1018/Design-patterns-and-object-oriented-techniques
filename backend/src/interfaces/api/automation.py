"""HTTP routes for automation."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.application.automation.dto import EvaluationDto, StrategyOptionDto, StrategyRuleDto
from src.application.automation.service import AutomationService
from src.application.locations.config_service import LocationNotFoundError
from src.domain.automation.errors import UnknownStrategyError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.automation_repository import (
    AutomationContextRepository,
    AutomationRuleRepository,
)

router = APIRouter(prefix="/api", tags=["automation"])


def get_service(session: Session = Depends(get_db)) -> AutomationService:
    return AutomationService(
        AutomationRuleRepository(session),
        AutomationContextRepository(session),
    )


class SetStrategyRequest(BaseModel):
    """Body of PUT /api/locations/{id}/automation.

    The key only. Which algorithm that names is the domain's business, and the
    router never looks inside the string.
    """

    strategy_key: str = Field(
        description="Which algorithm this location decides with.",
        examples=["conservative", "aggressive"],
    )


@router.get(
    "/automation/strategies",
    response_model=list[StrategyOptionDto],
    summary="List the available strategies",
)
def list_strategies(service: AutomationService = Depends(get_service)) -> list[StrategyOptionDto]:
    """Every registered algorithm, so the dropdown never hardcodes a key.

    Add a third strategy class and it appears here with no change to this file.
    """
    return service.list_strategies()


@router.get(
    "/locations/{location_id}/automation",
    response_model=StrategyRuleDto,
    summary="The strategy this location decides with",
)
def get_rule(
    location_id: UUID,
    service: AutomationService = Depends(get_service),
) -> StrategyRuleDto:
    try:
        return service.get_rule(location_id)
    except LocationNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error


@router.put(
    "/locations/{location_id}/automation",
    response_model=StrategyRuleDto,
    summary="Save the strategy for a location",
)
def set_strategy(
    location_id: UUID,
    payload: SetStrategyRequest,
    service: AutomationService = Depends(get_service),
) -> StrategyRuleDto:
    """Upsert, so saving twice replaces rather than fails.

    PUT because the body is the whole of the resource and sending it again
    changes nothing further. The UNIQUE on location_id makes that true in the
    database too, not only in the handler.
    """
    try:
        return service.set_strategy(location_id, payload.strategy_key)
    except LocationNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except UnknownStrategyError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


@router.post(
    "/locations/{location_id}/automation/evaluate",
    response_model=EvaluationDto,
    summary="Decide what this location needs right now",
)
def evaluate(
    location_id: UUID,
    service: AutomationService = Depends(get_service),
) -> EvaluationDto:
    """Evaluate with the persisted key. There is no query parameter to override it.

    POST rather than GET because the answer depends on the readings at this
    moment and must not be cached by a browser or a proxy. It writes nothing.
    """
    try:
        return service.evaluate(location_id)
    except LocationNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except UnknownStrategyError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error