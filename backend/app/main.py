"""FastAPI application factory."""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.modules.discovery.overpass import DiscoveryProviderError
from app.modules.discovery.router import router as discovery_router
from app.modules.evaluator.exceptions import EvaluatorDomainError
from app.modules.government.config import (
    get_government_settings,
    validate_government_startup,
)
from app.modules.government.exceptions import GovernmentDomainError

logger = logging.getLogger("namma_suvidha")


def _error(status_code: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "code": code})


def create_app() -> FastAPI:
    settings = get_settings()
    gov_settings = get_government_settings()
    configure_logging(settings.LOG_LEVEL)
    validate_government_startup(settings.APP_ENV, gov_settings)

    # Tags are declared explicitly so all module routers are visible in /docs.
    openapi_tags = [
        {"name": "health", "description": "Service and database health (implemented)."},
        {
            "name": "citizen",
            "description": "Citizen module — GPS & OpenStreetMap public toilet discovery.",
        },
        {
            "name": "evaluator",
            "description": "Evaluator onboarding, WebAuthn passkeys, inspection submission & admin review.",
        },
        {
            "name": "government",
            "description": "Government facility monitoring & feedback-driven cleaning.",
        },
        {
            "name": "admin",
            "description": "Internal Admin Audit Logs, Platform Analytics & KPI Overview.",
        },
    ]
    app = FastAPI(title=settings.APP_NAME, version=__version__, openapi_tags=openapi_tags)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(GovernmentDomainError)
    async def government_domain_error_handler(
        _: Request, exc: GovernmentDomainError
    ) -> JSONResponse:
        return _error(exc.status_code, exc.detail, exc.code)

    @app.exception_handler(EvaluatorDomainError)
    async def evaluator_domain_error_handler(
        _: Request, exc: EvaluatorDomainError
    ) -> JSONResponse:
        return _error(exc.status_code, exc.detail, exc.code)

    @app.exception_handler(DiscoveryProviderError)
    async def discovery_provider_error_handler(
        _: Request, exc: DiscoveryProviderError
    ) -> JSONResponse:
        return _error(exc.status_code, exc.detail, exc.code)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return _error(exc.status_code, str(exc.detail), f"http_{exc.status_code}")

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(422, str(exc.errors()), "validation_error")

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return _error(500, "Internal server error", "internal_error")

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    # Also mount discovery router under /api so GET /api/toilets/nearby and
    # GET /api/v1/toilets/nearby both resolve cleanly.
    app.include_router(discovery_router, prefix="/api", include_in_schema=False)

    # -------------------------------------------------------------------------
    # Mount Frontend SPA on the SAME host and port (Unified Single Localhost)
    # -------------------------------------------------------------------------
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            # Do not intercept API or Swagger docs
            if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
                raise HTTPException(status_code=404, detail="Not Found")
            file_candidate = frontend_dist / full_path
            if full_path and file_candidate.exists() and file_candidate.is_file():
                return FileResponse(file_candidate)
            return FileResponse(frontend_dist / "index.html")

    logger.info(
        "Starting %s env=%s database_url_set=%s",
        settings.APP_NAME,
        settings.APP_ENV,
        bool(settings.DATABASE_URL),
    )
    return app


app = create_app()

