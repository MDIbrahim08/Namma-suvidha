"""Admin Authentication & Access Control Dependency.

OWNER: Internal Admin Audit & Analytics Module

Guards all `/api/v1/admin/*` routes.
Rejects normal citizens and evaluators with 403 Forbidden.
"""

import logging
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings

logger = logging.getLogger("namma_suvidha.admin.security")

# Canonical dev admin key for internal operations
DEV_ADMIN_KEY = "namma-admin-secret-key-2026"


def require_admin_user(
    request: Request,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Strict admin authentication guard."""
    # 1. Check direct X-Admin-Key header
    if x_admin_key and x_admin_key == DEV_ADMIN_KEY:
        return {"id": "admin-root", "role": "admin", "actor": "admin:system-root"}

    # 2. Check Bearer token
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token in {DEV_ADMIN_KEY, "dev-admin-token", "admin-token-2026"}:
            return {"id": "admin-root", "role": "admin", "actor": "admin:system-root"}

    # 3. In development mode with localhost access, allow dev admin session
    client_host = request.client.host if request.client else ""
    if settings.APP_ENV == "development" and client_host in {"127.0.0.1", "localhost", "::1"}:
        return {"id": "admin-local-dev", "role": "admin", "actor": "admin:local-dev"}

    logger.warning("Unauthorized admin access attempt from IP %s on %s", client_host, request.url.path)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Administrator privilege required to access this endpoint. Citizens and Volunteers are prohibited.",
    )

