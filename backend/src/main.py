"""FastAPI application entry point for the smart greenhouse API."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from src.application.readings.sampler import SimulationSampler
from src.application.readings.service import ReadingIngest
from src.infrastructure.db import SessionLocal
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.reading_repository import ReadingRepository
from src.infrastructure.settings import get_settings
from src.interfaces.api.devices import router as devices_router
from src.interfaces.api.health import router as health_router
from src.interfaces.api.locations import router as locations_router
from src.interfaces.api.sensors import router as sensors_router

logger = logging.getLogger(__name__)

settings = get_settings()

# How often the sampler wakes up. Not the sampling interval itself: each device
# has its own, and this only has to be fine enough to notice when one is due.
# Five seconds matches the minimum interval the API accepts.
SAMPLER_TICK_SECONDS = 5


def _tick() -> int:
    """One sampler pass, with its own session.

    A session per tick, not one for the life of the process. A long-lived
    session holds a pooled connection open and serves whatever it cached the
    first time it read a row.
    """
    session = SessionLocal()
    try:
        devices = DeviceRepository(session)
        readings = ReadingRepository(session)
        sampler = SimulationSampler(devices, readings, ReadingIngest(devices, readings))
        return sampler.run_once(datetime.now(UTC))
    finally:
        session.close()


async def _sampler_loop() -> None:
    """Run the sampler forever, until the task is cancelled."""
    while True:
        await asyncio.sleep(SAMPLER_TICK_SECONDS)
        try:
            # to_thread, because the session and the repositories are
            # synchronous. Calling _tick directly would block the event loop,
            # which means blocking every HTTP request for the whole tick.
            written = await asyncio.to_thread(_tick)
            if written:
                logger.info("Sampler recorded %s reading(s)", written)
        except Exception:
            # A failed tick must not kill the loop. The next one is five
            # seconds away and the devices are still due.
            logger.exception("Sampler tick failed")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the sampler on boot, stop it on shutdown.

    Note this does not run under pytest. TestClient only fires lifespan events
    when it is used as a context manager, and the test modules build a plain
    module-level client. That is deliberate: the tests drive run_once with a
    fake clock, and a background sampler writing rows underneath them would
    make every count assertion flaky.
    """
    task = asyncio.create_task(_sampler_loop())
    logger.info("Simulation sampler started, ticking every %ss", SAMPLER_TICK_SECONDS)
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        logger.info("Simulation sampler stopped")


app = FastAPI(
    title="Smart Greenhouse API",
    description="Backend for the smart greenhouse dashboard.",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url=None,  # Swagger UI off - Scalar is the documented reference.
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(sensors_router)
app.include_router(devices_router)
app.include_router(locations_router)


@app.get("/", tags=["system"], summary="API discovery")
def read_root() -> dict[str, str]:
    return {
        "name": app.title,
        "version": app.version,
        "reference": "/scalar",
        "openapi": "/openapi.json",
        "health": "/health",
    }


@app.get("/scalar", include_in_schema=False)
def scalar_reference() -> HTMLResponse:
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)