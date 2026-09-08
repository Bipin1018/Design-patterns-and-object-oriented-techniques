"""Database engine, session factory and connectivity check.

Phase 1 has no ORM models. This module exists so the API can prove it reaches
PostgreSQL, and so Phase 2 can hang models and repositories off the same engine.
"""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from src.infrastructure.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# create_engine does not open a connection; pool_pre_ping discards dead ones,
# which matters when the Postgres container restarts under the running API.
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def check_database() -> bool:
    """Run SELECT 1. True if PostgreSQL answered, False on any connection error."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Database connectivity check failed: %s", exc)
        return False
    return True
