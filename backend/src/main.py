"""FastAPI application entry point for the smart greenhouse API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from src.infrastructure.settings import get_settings
from src.interfaces.api.health import router as health_router

settings = get_settings()

app = FastAPI(
    title="Smart Greenhouse API",
    description="Backend for the smart greenhouse dashboard. Phase 1 serves health only.",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url=None,  # Swagger UI off — Scalar is the documented reference.
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)


@app.get("/", tags=["system"], summary="API discovery")
def read_root() -> dict[str, str]:
    """Point clients at the reference, the schema and the health check."""
    return {
        "name": app.title,
        "version": app.version,
        "reference": "/scalar",
        "openapi": "/openapi.json",
        "health": "/health",
    }


@app.get("/scalar", include_in_schema=False)
def scalar_reference() -> HTMLResponse:
    """Serve the Scalar API reference. Excluded from the schema — it is a page, not an operation."""
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)
