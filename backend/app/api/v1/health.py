"""Health endpoints (implemented in Phase 0)."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.db.session import check_database_connection
from app.schemas.common import DatabaseHealthResponse, HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        env=settings.APP_ENV,
        version=__version__,
        timestamp=datetime.now(UTC),
    )


@router.get("/db", response_model=DatabaseHealthResponse)
def health_db() -> DatabaseHealthResponse:
    return DatabaseHealthResponse(**check_database_connection())

