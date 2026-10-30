"""Authentication and authorisation - PLACEHOLDER.

OWNER: Shabaz

Phase 1 will implement Supabase JWT verification, role guards (citizen /
evaluator / government / admin) and device-biometric hooks here.
This stub is intentionally NOT wired into any route in Phase 0.
"""

from fastapi import HTTPException, status


def get_current_user() -> None:
    """FastAPI dependency stub. Always raises 501 until Shabaz implements it."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentication not implemented — owned by Shabaz",
    )

