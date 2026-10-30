"""Adapter consuming the official facility score from `app.modules.intelligence`.

OWNER: Ibrahim (adapter) / Shubham (scoring engine owner)

Government NEVER computes a facility score. This adapter checks whether
`app.modules.intelligence` exposes `get_facility_score(facility_id)` (or an
in-memory override registered for tests/dev fixtures) and returns an
`OfficialScore | None`.
"""

from datetime import UTC, datetime

from app.modules import intelligence
from app.modules.government.domain import OfficialScore


class IntelligenceScoreProvider:
    """Consumes official facility scores from `app.modules.intelligence`."""

    def __init__(self) -> None:
        self._overrides: dict[str, OfficialScore] = {}

    def clear_overrides(self) -> None:
        self._overrides.clear()

    def register_override(self, facility_id: str, score: OfficialScore) -> None:
        self._overrides[facility_id] = score.model_copy(deep=True)

    def get_score(self, facility_id: str) -> OfficialScore | None:
        if facility_id in self._overrides:
            return self._overrides[facility_id].model_copy(deep=True)

        fn = getattr(intelligence, "get_facility_score", None)
        if callable(fn):
            raw = fn(facility_id)
            if raw is None:
                return None
            if isinstance(raw, OfficialScore):
                return raw
            if isinstance(raw, dict):
                return OfficialScore(
                    value=float(raw["value"]),
                    computed_at=raw.get("computed_at") or datetime.now(UTC),
                    source="intelligence",
                )
            if isinstance(raw, int | float):
                return OfficialScore(
                    value=float(raw),
                    computed_at=datetime.now(UTC),
                    source="intelligence",
                )
        return None
