"""Repository bundle factory for the Evaluator module (`memory` | `sql`).

OWNER: Ibrahim

Enforces Condition 2:
- In-memory storage is for development (`APP_ENV == 'development'`) and deterministic tests only.
- Production (`APP_ENV != 'development'`) MUST fail closed if SQL persistence is unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.core.config import get_settings
from app.modules.evaluator.exceptions import EvaluatorSchemaPendingError
from app.modules.evaluator.repositories.memory import (
    InMemoryAuditLogRepository,
    InMemoryEvaluatorCooldownRepository,
    InMemoryEvaluatorInspectionRepository,
    InMemoryEvaluatorTaskRepository,
    InMemoryEvaluatorUserRepository,
    InMemoryEvaluatorVerificationRepository,
    InMemoryWebAuthnChallengeRepository,
    InMemoryWebAuthnCredentialRepository,
)
from app.modules.evaluator.repositories.sql import SqlEvaluatorRepositories

logger = logging.getLogger("namma_suvidha.evaluator.repositories")


@dataclass
class EvaluatorRepositoryBundle:
    users: InMemoryEvaluatorUserRepository
    verifications: InMemoryEvaluatorVerificationRepository
    credentials: InMemoryWebAuthnCredentialRepository
    challenges: InMemoryWebAuthnChallengeRepository
    audit_logs: InMemoryAuditLogRepository
    tasks: InMemoryEvaluatorTaskRepository
    cooldowns: InMemoryEvaluatorCooldownRepository
    inspections: InMemoryEvaluatorInspectionRepository
    data_source: Literal["memory", "sql"] = "memory"

    def clear_all(self) -> None:
        self.users.clear()
        self.verifications.clear()
        self.credentials.clear()
        self.challenges.clear()
        self.audit_logs.clear()
        self.tasks.clear()
        self.cooldowns.clear()
        self.inspections.clear()


_MEMORY_BUNDLE: EvaluatorRepositoryBundle | None = None


def get_evaluator_memory_bundle() -> EvaluatorRepositoryBundle:
    global _MEMORY_BUNDLE
    if _MEMORY_BUNDLE is None:
        _MEMORY_BUNDLE = EvaluatorRepositoryBundle(
            users=InMemoryEvaluatorUserRepository(),
            verifications=InMemoryEvaluatorVerificationRepository(),
            credentials=InMemoryWebAuthnCredentialRepository(),
            challenges=InMemoryWebAuthnChallengeRepository(),
            audit_logs=InMemoryAuditLogRepository(),
            tasks=InMemoryEvaluatorTaskRepository(),
            cooldowns=InMemoryEvaluatorCooldownRepository(),
            inspections=InMemoryEvaluatorInspectionRepository(),
            data_source="memory",
        )
    return _MEMORY_BUNDLE


def get_evaluator_repository_bundle(
    backend: Literal["memory", "sql"] = "memory",
    *,
    app_env: str | None = None,
) -> EvaluatorRepositoryBundle:
    resolved_env = app_env or get_settings().APP_ENV

    if resolved_env != "development" and backend == "memory":
        raise EvaluatorSchemaPendingError(
            "EVAL_REPOSITORY_BACKEND='memory' is forbidden in production. "
            "Production must use SQL persistence and fail closed if unavailable."
        )

    if backend == "sql":
        try:
            SqlEvaluatorRepositories()
        except EvaluatorSchemaPendingError as exc:
            if resolved_env != "development":
                # Fail closed in production!
                raise
            logger.warning(
                "EVAL_REPOSITORY_BACKEND=sql requested in development, but schema is "
                "pending (%s); falling back to in-memory repositories for development.",
                exc.detail,
            )

    return get_evaluator_memory_bundle()


__all__ = [
    "EvaluatorRepositoryBundle",
    "SqlEvaluatorRepositories",
    "get_evaluator_memory_bundle",
    "get_evaluator_repository_bundle",
]

