"""SQL repository skeleton for Government Monitoring.

OWNER: Ibrahim (adapter) / Shubham (ORM schema owner)

No ORM models exist in Phase 2. Constructing `SqlGovernmentRepositories` raises
`GovernmentSchemaPendingError` pointing to `docs/proposals/GOVERNMENT_DATA_REQUIREMENTS.md`.
"""

from app.modules.government.exceptions import GovernmentSchemaPendingError


class SqlGovernmentRepositories:
    """Placeholder SQL repository bundle awaiting Shubham's approved ORM schema."""

    def __init__(self) -> None:
        raise GovernmentSchemaPendingError(
            "SQL repositories cannot be initialised because no ORM models exist yet. "
            "See docs/proposals/GOVERNMENT_DATA_REQUIREMENTS.md (AWAITING SHUBHAM'S APPROVAL)."
        )

