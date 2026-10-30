"""SQL-ready repository adapter for Evaluator Authentication, WebAuthn,
ID Verification, and Audit Logging.

OWNER: Ibrahim (SQL repository adapter) / Shubham (Database Schema & ORM Owner)

Strictly checks that `DATABASE_URL` is configured and that Shubham & Shabaz's
approved schema migration (`docs/proposals/sql/20261031_evaluator_auth_schema.sql`)
has been applied. Never executes DDL or migrations automatically. Fails closed
with `EvaluatorSchemaPendingError` if SQL persistence is unavailable.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_engine
from app.modules.evaluator.exceptions import EvaluatorSchemaPendingError

REQUIRED_EVALUATOR_AUTH_TABLES: tuple[str, ...] = (
    "users",
    "evaluator_verifications",
    "webauthn_credentials",
    "webauthn_challenges",
    "audit_logs",
    "evaluator_tasks",
    "evaluator_cooldowns",
    "inspections",
)


class SqlEvaluatorRepositories:
    """SQL repository adapter verifying connectivity and required Stage 2 tables."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.DATABASE_URL.strip():
            raise EvaluatorSchemaPendingError(
                "SQL persistence requested for Evaluator module, but DATABASE_URL is not "
                "configured."
            )

        try:
            engine = get_engine()
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = 'public'
                        """
                    )
                ).fetchall()
                existing_tables = {str(r[0]) for r in rows}
        except SQLAlchemyError as exc:
            raise EvaluatorSchemaPendingError(
                "Unable to connect to SQL database for Evaluator repositories."
            ) from exc

        missing = [
            tbl
            for tbl in REQUIRED_EVALUATOR_AUTH_TABLES
            if tbl not in existing_tables
        ]
        if missing:
            raise EvaluatorSchemaPendingError(
                f"Evaluator SQL schema migration is pending approval/execution. "
                f"Missing tables in public schema: {missing}. "
                f"See docs/proposals/sql/20261031_evaluator_auth_schema.sql "
                f"(AWAITING SHUBHAM & SHABAZ'S APPROVAL)."
            )

