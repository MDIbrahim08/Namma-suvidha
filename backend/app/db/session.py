"""Database engine, session factory and connectivity check.

The engine is created lazily on first use so the app starts even when
DATABASE_URL is empty or the database is unreachable.
"""

import re
from collections.abc import Iterator
from functools import lru_cache
from typing import TypedDict

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_CREDENTIAL_IN_URL_RE = re.compile(r"(postgresql(?:\+\w+)?://[^:/@\s]+:)([^@\s]+)(@)")


def sanitize_db_error_message(raw: str) -> str:
    """Redact any embedded password in a database connection string or exception message."""
    if not raw:
        return ""
    first_line = raw.splitlines()[0]
    return _CREDENTIAL_IN_URL_RE.sub(r"\1***REDACTED***\3", first_line)


class DatabaseStatus(TypedDict):
    connected: bool
    postgis_available: bool
    postgis_version: str | None
    error: str | None


@lru_cache
def get_engine() -> Engine:
    url = get_settings().DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    connect_args: dict[str, object] = {"connect_timeout": 5}
    if url.startswith("postgresql+psycopg://"):
        # Required for Supabase Supavisor transaction pooler (port 6543)
        connect_args["prepare_threshold"] = None
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def SessionLocal() -> Session:  # noqa: N802 - conventional name
    return get_sessionmaker()()


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> DatabaseStatus:
    """Run SELECT 1 and SELECT PostGIS_Version(). Never raises."""
    result: DatabaseStatus = {
        "connected": False,
        "postgis_available": False,
        "postgis_version": None,
        "error": None,
    }
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            result["connected"] = True
            try:
                version = conn.execute(text("SELECT PostGIS_Version()")).scalar()
                result["postgis_available"] = True
                result["postgis_version"] = str(version)
            except Exception as exc:  # PostGIS extension missing
                result["error"] = f"PostGIS not available: {type(exc).__name__}"
    except Exception as exc:
        sanitized = sanitize_db_error_message(str(exc))
        result["error"] = f"{type(exc).__name__}: {sanitized}"
    return result

