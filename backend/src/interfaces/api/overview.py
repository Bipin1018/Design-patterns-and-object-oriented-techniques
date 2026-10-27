"""HTTP route for the location overview."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.locations.config_service import LocationNotFoundError
from src.application.overview.dto import LocationOverviewDto
from src.application.overview.facade import LocationOverviewFacade
from src.domain.automation.errors import UnknownStrategyError
from src.interfaces.api.overview_deps import get_overview_facade

router = APIRouter(prefix="/api", tags=["overview"])


@router.get(
    "/locations/{location_id}/overview",
    response_model=LocationOverviewDto,
    summary="Everything the dashboard shows for one location",
)
def get_overview(
    location_id: UUID,
    facade: LocationOverviewFacade = Depends(get_overview_facade),
) -> LocationOverviewDto:
    """Location, assigned devices, newest readings, saved strategy and a fresh recommendation."""
    try:
        return facade.get_overview(location_id)
    except LocationNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except UnknownStrategyError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error