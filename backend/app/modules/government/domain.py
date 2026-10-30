"""Pydantic v2 domain read models for the Government Monitoring module.

OWNER: Ibrahim

These are domain/read models (NOT SQLAlchemy ORM models). When Shubham's ORM
schema lands, `repositories/sql.py` will map ORM rows into these models.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.government.enums import (
    CleanlinessVerdict,
    ConditionBand,
    FeedbackCategory,
    FeedbackChannel,
    FeedbackSentiment,
    FeedbackSource,
    IssueStatus,
    IssueType,
    NotificationChannel,
    NotificationStatus,
    TriageLevel,
    VerificationStatus,
)

CLASSIFICATION_NOTE = (
    "Government triage classification — not an official facility or cleanliness score"
)
EVALUATION_NO_BACKFILL_NOTE = (
    "Processed latest complete window only; earlier missed windows are not backfilled in this MVP."
)


class ResponsibleParty(BaseModel):
    name: str
    organization: str | None = None
    role_title: str | None = None
    email: str | None = None
    phone: str | None = None
    verified: bool = False


def redact_responsible_party(
    party: ResponsibleParty | None,
    viewer_role: str | set[str] | list[str] | None,
) -> ResponsibleParty | None:
    """Strip authority/operator contact details unless viewer is government or admin.

    Reusable by the Citizen module so operator emails/phones are never exposed
    to citizens.
    """
    if party is None:
        return None
    if isinstance(viewer_role, str):
        roles = {viewer_role.lower()}
    elif viewer_role is None:
        roles = set()
    else:
        roles = {str(r).lower() for r in viewer_role}

    if roles & {"government", "admin"}:
        return party.model_copy()

    return party.model_copy(update={"email": None, "phone": None})


class InspectionSummary(BaseModel):
    inspection_id: str
    facility_id: str
    evaluator_id: str | None = None
    inspected_at: datetime
    checklist_passed: bool | None = None
    summary_note: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class OfficialScore(BaseModel):
    """Official facility score consumed from `app.modules.intelligence`."""

    value: float = Field(ge=0.0, le=100.0)
    computed_at: datetime
    source: Literal["intelligence"] = "intelligence"


class DataQualityFlags(BaseModel):
    inspection_stale: bool = False
    never_inspected: bool = False
    missing_operator: bool = False
    missing_location: bool = False
    low_usage: bool = False
    cleanliness_unknown: bool = False


class CleanlinessResponse(BaseModel):
    id: str
    facility_id: str
    is_clean: bool
    channel: FeedbackChannel
    created_at: datetime
    respondent_hash: str | None = None


class CleanlinessWindow(BaseModel):
    facility_id: str
    window_start: datetime
    window_end: datetime
    yes_count: int = 0
    no_count: int = 0
    total: int = 0
    negative_ratio: float = 0.0
    verdict: CleanlinessVerdict
    action: Literal["none", "alert", "escalate", "insufficient_data"]
    reasons: list[str] = Field(default_factory=list)


class TriageResult(BaseModel):
    """Government triage classification (NOT a facility or cleanliness score)."""

    level: TriageLevel = Field(
        description=(
            "Government triage classification for ordering follow-up work. "
            "Not a cleanliness score or official facility score."
        )
    )
    reasons: list[str] = Field(default_factory=list)
    responsibility_unverified: bool = False
    classification_note: str = CLASSIFICATION_NOTE


class FacilityRecord(BaseModel):
    """Underlying facility record stored in a repository."""

    id: str
    name: str
    ward: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    verification_status: VerificationStatus = VerificationStatus.unverified
    responsible_party: ResponsibleParty | None = None


class FacilitySummary(BaseModel):
    id: str
    name: str
    ward: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    verification_status: VerificationStatus
    condition: ConditionBand
    official_score: OfficialScore | None = None
    latest_inspected_at: datetime | None = None
    data_quality: DataQualityFlags
    triage: TriageResult = Field(
        description=(
            "Government triage classification (urgent/high/normal/unranked) — "
            "not an official facility or cleanliness score."
        )
    )


class FacilityDetail(BaseModel):
    id: str
    name: str
    ward: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    verification_status: VerificationStatus
    condition: ConditionBand
    responsible_party: ResponsibleParty | None = None
    latest_inspection: InspectionSummary | None = None
    official_score: OfficialScore | None = None
    data_quality: DataQualityFlags
    latest_cleanliness_window: CleanlinessWindow | None = None
    triage: TriageResult = Field(
        description=(
            "Government triage classification (urgent/high/normal/unranked) — "
            "not an official facility or cleanliness score."
        )
    )


class CitizenFeedbackItem(BaseModel):
    id: str
    facility_id: str
    ward: str | None = None
    source: Literal[FeedbackSource.citizen_feedback] = FeedbackSource.citizen_feedback
    category: FeedbackCategory
    sentiment: FeedbackSentiment
    severity: int = Field(default=1, ge=1, le=5)
    channel: FeedbackChannel = FeedbackChannel.app
    comment: str | None = None
    reporter_hash: str | None = None
    linked_issue_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    age_hours: float = 0.0


class RepeatedComplaintCluster(BaseModel):
    facility_id: str
    facility_name: str | None = None
    ward: str | None = None
    category: FeedbackCategory
    count: int
    distinct_reporters: int
    first_seen: datetime
    last_seen: datetime


class IssueAuditEntry(BaseModel):
    from_status: IssueStatus | None
    to_status: IssueStatus
    actor_id: str
    note: str
    timestamp: datetime


class NotificationRecord(BaseModel):
    id: str
    issue_id: str
    channel: NotificationChannel = NotificationChannel.email
    recipient: str
    status: NotificationStatus
    created_at: datetime
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    provider_message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class MaintenanceIssue(BaseModel):
    id: str
    type: IssueType
    status: IssueStatus
    facility_id: str
    ward: str | None = None
    category: FeedbackCategory
    triage_level: TriageLevel = Field(
        description="Government triage classification at issue creation/update — not a score."
    )
    summary: str
    responsibility_unverified: bool = False
    consecutive_negative_windows: int = 0
    verification_requested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    history: list[IssueAuditEntry] = Field(default_factory=list)
    notifications: list[NotificationRecord] = Field(default_factory=list)


class OverviewStatistics(BaseModel):
    total_facilities: int = 0
    recommended: int = 0
    needing_attention: int = 0
    unscored: int = 0
    unverified: int = 0
    pending_complaints: int = 0
    active_issues: int = 0
    escalated_issues: int = 0
    resolved_issues: int = 0
    recent_inspections: int = 0
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0
    cleanliness_alerts_last_24h: int = 0
    facilities_low_usage: int = 0
    facilities_cleanliness_unknown: int = 0
    generated_at: datetime
    data_source: Literal["memory", "sql"] = "memory"


class EvaluationSummary(BaseModel):
    window_start: datetime
    window_end: datetime
    facilities_considered: int = 0
    windows_saved: int = 0
    skipped_existing: int = 0
    clean: int = 0
    needs_cleaning: int = 0
    insufficient_data: int = 0
    low_usage_flagged: int = 0
    alerts_created: int = 0
    alerts_emailed: int = 0
    alerts_without_recipient: int = 0
    escalations: int = 0
    affected_facility_ids: list[str] = Field(default_factory=list)
    affected_issue_ids: list[str] = Field(default_factory=list)
    note: str = EVALUATION_NO_BACKFILL_NOTE


class MaintenanceDetectionSummary(BaseModel):
    evaluated_at: datetime
    facilities_considered: int = 0
    issues_created: int = 0
    existing_issues_noted: int = 0
    created_issue_ids: list[str] = Field(default_factory=list)

