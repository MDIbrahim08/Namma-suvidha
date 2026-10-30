"""Citizen feedback listing and repeated-complaint cluster detection.

OWNER: Ibrahim

Strictly separates citizen feedback (`source=citizen_feedback`) from evaluator
inspections. Evaluator findings are never counted or returned here.
"""

from datetime import datetime

from app.modules.government.config import GovernmentSettings
from app.modules.government.domain import (
    CitizenFeedbackItem,
    CleanlinessWindow,
    RepeatedComplaintCluster,
)
from app.modules.government.enums import FeedbackSentiment, FeedbackSource
from app.modules.government.exceptions import ResourceNotFoundError
from app.modules.government.interfaces import (
    CleanlinessRepository,
    FacilityRepository,
    FeedbackFilterParams,
    FeedbackRepository,
)


def _with_age_hours(item: CitizenFeedbackItem, now: datetime) -> CitizenFeedbackItem:
    delta_seconds = max(0.0, (now - item.created_at).total_seconds())
    age_hours = round(delta_seconds / 3600.0, 2)
    return item.model_copy(
        update={
            "source": FeedbackSource.citizen_feedback,
            "age_hours": age_hours,
        }
    )


class FeedbackService:
    def __init__(
        self,
        facility_repo: FacilityRepository,
        feedback_repo: FeedbackRepository,
        cleanliness_repo: CleanlinessRepository,
        settings: GovernmentSettings,
    ) -> None:
        self._facilities = facility_repo
        self._feedback = feedback_repo
        self._cleanliness = cleanliness_repo
        self._settings = settings

    def list_feedback(
        self, filters: FeedbackFilterParams, now: datetime
    ) -> list[CitizenFeedbackItem]:
        items = self._feedback.list(filters)
        return [_with_age_hours(item, now) for item in items]

    def list_facility_feedback_with_meta(
        self,
        facility_id: str,
        since: datetime | None,
        now: datetime,
    ) -> tuple[list[CitizenFeedbackItem], dict[str, int], list[CleanlinessWindow]]:
        facility = self._facilities.get(facility_id)
        if facility is None:
            raise ResourceNotFoundError(f"Facility '{facility_id}' not found")

        raw_items = self._feedback.list_for_facility(facility_id, since=since)
        items = [_with_age_hours(item, now) for item in raw_items]

        breakdown = {
            "positive": sum(
                1 for i in items if i.sentiment == FeedbackSentiment.positive
            ),
            "neutral": sum(
                1 for i in items if i.sentiment == FeedbackSentiment.neutral
            ),
            "negative": sum(
                1 for i in items if i.sentiment == FeedbackSentiment.negative
            ),
        }
        windows = self._cleanliness.list_windows(
            facility_id=facility_id, since=since
        )
        return items, breakdown, windows

    def repeated_clusters(
        self,
        now: datetime,
        facility_id: str | None = None,
        ward: str | None = None,
    ) -> list[RepeatedComplaintCluster]:
        clusters = self._feedback.repeated_clusters(
            now=now,
            window_days=self._settings.REPEAT_WINDOW_DAYS,
            min_count=self._settings.REPEAT_MIN_COUNT,
            min_reporters=self._settings.REPEAT_MIN_REPORTERS,
            facility_id=facility_id,
        )
        if ward:
            clusters = [c for c in clusters if c.ward == ward]
        return clusters

