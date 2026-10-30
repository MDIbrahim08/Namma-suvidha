"""Repository bundle factory for Government Monitoring (`memory` | `sql`).

OWNER: Ibrahim
"""

import logging
from dataclasses import dataclass
from typing import Literal

from app.modules.government.exceptions import GovernmentSchemaPendingError
from app.modules.government.repositories.memory import (
    InMemoryCleanlinessRepository,
    InMemoryFacilityRepository,
    InMemoryFeedbackRepository,
    InMemoryIssueRepository,
)
from app.modules.government.repositories.sql import SqlGovernmentRepositories

logger = logging.getLogger("namma_suvidha.government.repositories")


@dataclass
class RepositoryBundle:
    facilities: InMemoryFacilityRepository
    feedback: InMemoryFeedbackRepository
    cleanliness: InMemoryCleanlinessRepository
    issues: InMemoryIssueRepository
    data_source: Literal["memory", "sql"] = "memory"

    def clear_all(self) -> None:
        self.facilities.clear()
        self.feedback.clear()
        self.cleanliness.clear()
        self.issues.clear()


_MEMORY_BUNDLE: RepositoryBundle | None = None


def get_memory_bundle() -> RepositoryBundle:
    global _MEMORY_BUNDLE
    if _MEMORY_BUNDLE is None:
        fac = InMemoryFacilityRepository()
        _MEMORY_BUNDLE = RepositoryBundle(
            facilities=fac,
            feedback=InMemoryFeedbackRepository(facility_repo=fac),
            cleanliness=InMemoryCleanlinessRepository(),
            issues=InMemoryIssueRepository(),
            data_source="memory",
        )
    return _MEMORY_BUNDLE


def get_repository_bundle(backend: Literal["memory", "sql"] = "memory") -> RepositoryBundle:
    if backend == "sql":
        try:
            SqlGovernmentRepositories()
        except GovernmentSchemaPendingError as exc:
            logger.warning(
                "GOV_REPOSITORY_BACKEND=sql requested, but schema is pending (%s); "
                "falling back to in-memory repositories.",
                exc,
            )
    return get_memory_bundle()

