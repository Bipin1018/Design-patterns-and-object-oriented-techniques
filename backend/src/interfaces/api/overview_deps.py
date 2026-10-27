"""Builds the overview facade for one request."""

from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.automation.service import AutomationService
from src.application.overview.facade import LocationOverviewFacade
from src.infrastructure.db import get_db
from src.infrastructure.persistence.automation_repository import (
    AutomationContextRepository,
    AutomationRuleRepository,
)
from src.infrastructure.persistence.overview_repository import OverviewRepository


def get_overview_facade(session: Session = Depends(get_db)) -> LocationOverviewFacade:
    automation = AutomationService(
        AutomationRuleRepository(session),
        AutomationContextRepository(session),
    )
    return LocationOverviewFacade(OverviewRepository(session), automation)