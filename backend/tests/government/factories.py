"""Deterministic test clock and factory builders for Government Monitoring tests."""

from datetime import UTC, datetime, timedelta

from app.modules.government.domain import (
    CitizenFeedbackItem,
    CleanlinessResponse,
    FacilityRecord,
    InspectionSummary,
    OfficialScore,
    ResponsibleParty,
)
from app.modules.government.enums import (
    FeedbackCategory,
    FeedbackChannel,
    FeedbackSentiment,
    VerificationStatus,
)


class FixedClock:
    def __init__(
        self, initial: datetime = datetime(2026, 10, 30, 12, 30, 0, tzinfo=UTC)
    ) -> None:
        self._now = initial

    def now(self) -> datetime:
        return self._now

    def set(self, new_now: datetime) -> None:
        self._now = new_now

    def advance(self, **kwargs: float) -> datetime:
        self._now = self._now + timedelta(**kwargs)
        return self._now


def make_facility(
    facility_id: str = "fac-1",
    *,
    name: str = "Test Public Toilet",
    ward: str = "Ward-1",
    address: str | None = "MG Road, Bengaluru",
    lat: float | None = 12.9750,
    lng: float | None = 77.6050,
    verification_status: VerificationStatus = VerificationStatus.verified,
    operator_email: str | None = "operator@example.org",
    operator_phone: str | None = "+91-80-11112222",
    operator_verified: bool = True,
    with_operator: bool = True,
) -> FacilityRecord:
    party = (
        ResponsibleParty(
            name="Sanitation Operator",
            organization="Civic Sanitation Unit",
            role_title="Supervisor",
            email=operator_email,
            phone=operator_phone,
            verified=operator_verified,
        )
        if with_operator
        else None
    )
    return FacilityRecord(
        id=facility_id,
        name=name,
        ward=ward,
        address=address,
        lat=lat,
        lng=lng,
        verification_status=verification_status,
        responsible_party=party,
    )


def make_inspection(
    inspection_id: str = "insp-1",
    facility_id: str = "fac-1",
    *,
    inspected_at: datetime,
    checklist_passed: bool = True,
    evidence_ids: list[str] | None = None,
) -> InspectionSummary:
    return InspectionSummary(
        inspection_id=inspection_id,
        facility_id=facility_id,
        evaluator_id="eval-1",
        inspected_at=inspected_at,
        checklist_passed=checklist_passed,
        summary_note="Inspection note",
        evidence_ids=evidence_ids or ["ev-1"],
    )


def make_score(
    value: float = 80.0,
    *,
    computed_at: datetime = datetime(2026, 10, 30, 10, 0, 0, tzinfo=UTC),
) -> OfficialScore:
    return OfficialScore(value=value, computed_at=computed_at, source="intelligence")


def make_feedback(
    feedback_id: str = "fb-1",
    facility_id: str = "fac-1",
    *,
    ward: str = "Ward-1",
    category: FeedbackCategory = FeedbackCategory.cleanliness_hygiene,
    sentiment: FeedbackSentiment = FeedbackSentiment.negative,
    severity: int = 3,
    channel: FeedbackChannel = FeedbackChannel.app,
    reporter_hash: str = "rep-1",
    linked_issue_id: str | None = None,
    created_at: datetime = datetime(2026, 10, 30, 11, 0, 0, tzinfo=UTC),
) -> CitizenFeedbackItem:
    return CitizenFeedbackItem(
        id=feedback_id,
        facility_id=facility_id,
        ward=ward,
        category=category,
        sentiment=sentiment,
        severity=severity,
        channel=channel,
        comment="Feedback comment",
        reporter_hash=reporter_hash,
        linked_issue_id=linked_issue_id,
        evidence_ids=[f"ev-{feedback_id}"],
        created_at=created_at,
    )


def make_cleanliness_response(
    response_id: str,
    facility_id: str,
    *,
    is_clean: bool,
    created_at: datetime,
    channel: FeedbackChannel = FeedbackChannel.qr,
    respondent_hash: str | None = None,
) -> CleanlinessResponse:
    return CleanlinessResponse(
        id=response_id,
        facility_id=facility_id,
        is_clean=is_clean,
        channel=channel,
        created_at=created_at,
        respondent_hash=respondent_hash,
    )

