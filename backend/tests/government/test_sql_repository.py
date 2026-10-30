"""SQL repository tests — skipped until Shubham's ORM models and PostGIS are present."""

import pytest

from app.db.base import Base
from app.modules.government.exceptions import GovernmentSchemaPendingError
from app.modules.government.repositories import get_repository_bundle
from app.modules.government.repositories.sql import SqlGovernmentRepositories


def test_sql_skeleton_raises_schema_pending_and_factory_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(GovernmentSchemaPendingError, match="AWAITING SHUBHAM'S APPROVAL"):
        SqlGovernmentRepositories()

    bundle = get_repository_bundle("sql")
    assert bundle.data_source == "memory"
    assert any("falling back to in-memory" in r.message for r in caplog.records)


@pytest.mark.skipif(
    len(Base.metadata.tables) == 0,
    reason=(
        "Awaiting Shubham's ORM models and live PostGIS database "
        "(see docs/proposals/GOVERNMENT_DATA_REQUIREMENTS.md)"
    ),
)
def test_sql_repository_against_postgis() -> None:
    """Placeholder for live SQL repository queries once Shubham's schema is merged."""
    assert len(Base.metadata.tables) > 0
