"""Generic response envelopes shared across the API.

Mirrored in frontend/src/lib/api/types.ts - keep both in sync.
"""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    version: str
    timestamp: datetime


class DatabaseHealthResponse(BaseModel):
    connected: bool
    postgis_available: bool
    postgis_version: str | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    detail: str
    code: str

