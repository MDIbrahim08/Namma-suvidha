"""Facility monitoring service (list, filter, detail, data-quality flags).

OWNER: Ibrahim
"""

import math
from datetime import datetime, timedelta

from app.modules.government.config import GovernmentSettings
from app.modules.government.domain import (
    DataQualityFlags,
    FacilityDetail,
    FacilityRecord,
    FacilitySummary,
    OfficialScore,
    redact_responsible_party,
)
from app.modules.government.enums import (
    ConditionBand,
    FeedbackCategory,
    IssueType,
    VerificationStatus,
)
from app.modules.government.exceptions import ResourceNotFoundError
from app.modules.government.interfaces import (
    CleanlinessRepository,
    FacilityFilterParams,
    FacilityRepository,
    FacilityScoreProvider,
    FeedbackRepository,
    IssueRepository,
)
from app.modules.government.services.cleanliness import check_facility_low_usage
from app.modules.government.services.priority import classify_facility_triage


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two WGS84 coordinates."""
    radius = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * radius * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def compute_condition_band(
    score: OfficialScore | None, settings: GovernmentSettings
) -> ConditionBand:
    """Map an official intelligence score into a display band (`unscored` when None)."""
    if score is None:
        return ConditionBand.unscored
    if score.value >= settings.SCORE_RECOMMENDED_MIN:
        return ConditionBand.recommended
    if score.value <= settings.SCORE_ATTENTION_MAX:
        return ConditionBand.attention
    return ConditionBand.moderate


class FacilityService:
    def __init__(
        self,
        facility_repo: FacilityRepository,
        feedback_repo: FeedbackRepository,
        cleanliness_repo: CleanlinessRepository,
        issue_repo: IssueRepository,
        score_provider: FacilityScoreProvider,
        settings: GovernmentSettings,
    ) -> None:
        self._facilities = facility_repo
        self._feedback = feedback_repo
        self._cleanliness = cleanliness_repo
        self._issues = issue_repo
        self._scores = score_provider
        self._settings = settings

    def _build_flags_and_triage(
        self, record: FacilityRecord, now: datetime
    ) -> tuple[DataQualityFlags, OfficialScore | None, ConditionBand, datetime | None]:
        latest_insp = self._facilities.latest_inspection(record.id)
        never_inspected = latest_insp is None
        stale_cutoff = now - timedelta(days=self._settings.INSPECTION_STALE_DAYS)
        inspection_stale = (
            latest_insp is not None and latest_insp.inspected_at < stale_cutoff
        )

        has_verified_operator = (
            record.verification_status == VerificationStatus.verified
            and record.responsible_party is not None
            and record.responsible_party.verified
        )
        missing_operator = not has_verified_operator
        missing_location = record.lat is None or record.lng is None

        low_usage, cleanliness_unknown = check_facility_low_usage(
            self._cleanliness, record.id, now, self._settings
        )

        flags = DataQualityFlags(
            inspection_stale=inspection_stale,
            never_inspected=never_inspected,
            missing_operator=missing_operator,
            missing_location=missing_location,
            low_usage=low_usage,
            cleanliness_unknown=cleanliness_unknown,
        )
        score = self._scores.get_score(record.id)
        condition = compute_condition_band(score, self._settings)
        return (
            flags,
            score,
            condition,
            latest_insp.inspected_at if latest_insp else None,
        )

    def _compute_triage(
        self,
        record: FacilityRecord,
        score: OfficialScore | None,
        flags: DataQualityFlags,
        now: datetime,
    ):
        clusters = self._feedback.repeated_clusters(
            now=now,
            window_days=self._settings.REPEAT_WINDOW_DAYS,
            min_count=self._settings.REPEAT_MIN_COUNT,
            min_reporters=self._settings.REPEAT_MIN_REPORTERS,
            facility_id=record.id,
        )
        active_cleaning = self._issues.find_open(
            record.id, IssueType.cleaning, FeedbackCategory.cleanliness_hygiene
        )
        feedback_items = self._feedback.list_for_facility(record.id)
        low_usage_start = now - timedelta(hours=self._settings.CLEAN_LOW_USAGE_HOURS)
        recent_cleanliness_count = self._cleanliness.count_responses(
            record.id, low_usage_start, now
        )
        has_any_feedback = bool(feedback_items) or recent_cleanliness_count > 0

        return classify_facility_triage(
            official_score=score,
            repeated_clusters=clusters,
            active_cleaning_issue_status=(
                active_cleaning.status if active_cleaning else None
            ),
            has_any_feedback=has_any_feedback,
            inspection_stale=flags.inspection_stale,
            low_usage=flags.low_usage,
            verification_status=record.verification_status,
            settings=self._settings,
        )

    def list_facilities(
        self, filters: FacilityFilterParams, now: datetime
    ) -> list[FacilitySummary]:
        records = self._facilities.list()
        summaries: list[FacilitySummary] = []

        for record in records:
            if filters.ward and record.ward != filters.ward:
                continue
            if (
                filters.verification_status
                and record.verification_status != filters.verification_status
            ):
                continue

            if (
                filters.lat is not None
                and filters.lng is not None
                and filters.radius_m is not None
            ):
                if record.lat is None or record.lng is None:
                    continue
                dist = haversine_distance_m(
                    filters.lat, filters.lng, record.lat, record.lng
                )
                if dist > filters.radius_m:
                    continue

            flags, score, condition, latest_inspected_at = self._build_flags_and_triage(
                record, now
            )

            if filters.condition and condition != filters.condition:
                continue
            if filters.stale_only and not flags.inspection_stale:
                continue
            if filters.low_usage_only and not flags.low_usage:
                continue

            triage = self._compute_triage(record, score, flags, now)

            summaries.append(
                FacilitySummary(
                    id=record.id,
                    name=record.name,
                    ward=record.ward,
                    address=record.address,
                    lat=record.lat,
                    lng=record.lng,
                    verification_status=record.verification_status,
                    condition=condition,
                    official_score=score,
                    latest_inspected_at=latest_inspected_at,
                    data_quality=flags,
                    triage=triage,
                )
            )
        return summaries

    def get_facility_detail(
        self,
        facility_id: str,
        now: datetime,
        viewer_roles: set[str] | None = None,
    ) -> FacilityDetail:
        record = self._facilities.get(facility_id)
        if record is None:
            raise ResourceNotFoundError(f"Facility '{facility_id}' not found")

        flags, score, condition, _ = self._build_flags_and_triage(record, now)
        triage = self._compute_triage(record, score, flags, now)
        latest_insp = self._facilities.latest_inspection(facility_id)
        latest_window = self._cleanliness.latest_window(facility_id)

        party = None
        if (
            record.verification_status == VerificationStatus.verified
            and record.responsible_party is not None
            and record.responsible_party.verified
        ):
            party = redact_responsible_party(
                record.responsible_party, viewer_roles or {"government"}
            )

        return FacilityDetail(
            id=record.id,
            name=record.name,
            ward=record.ward,
            address=record.address,
            lat=record.lat,
            lng=record.lng,
            verification_status=record.verification_status,
            condition=condition,
            responsible_party=party,
            latest_inspection=latest_insp,
            official_score=score,
            data_quality=flags,
            latest_cleanliness_window=latest_window,
            triage=triage,
        )

