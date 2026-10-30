"""Government triage classification. Orders follow-up work for government staff.
It is NOT a cleanliness score, NOT a facility score, and NOT a replacement for
the intelligence module's official scoring engine owned by Shubham. It consumes
the official score and never recomputes it.

OWNER: Ibrahim
"""

from app.modules.government.config import GovernmentSettings
from app.modules.government.domain import (
    CLASSIFICATION_NOTE,
    OfficialScore,
    RepeatedComplaintCluster,
    TriageResult,
)
from app.modules.government.enums import (
    FeedbackCategory,
    IssueStatus,
    TriageLevel,
    VerificationStatus,
)

URGENT_CLUSTER_CATEGORIES = {
    FeedbackCategory.safety,
    FeedbackCategory.accessibility,
    FeedbackCategory.locked_facility,
}


def classify_facility_triage(
    *,
    official_score: OfficialScore | None,
    repeated_clusters: list[RepeatedComplaintCluster],
    active_cleaning_issue_status: IssueStatus | None,
    has_any_feedback: bool,
    inspection_stale: bool,
    low_usage: bool,
    verification_status: VerificationStatus,
    settings: GovernmentSettings,
) -> TriageResult:
    """Compute the Government triage classification (`urgent`/`high`/`normal`/`unranked`).

    Never computes a facility or cleanliness score.
    """
    reasons: list[str] = []
    urgent = False
    high = False

    if active_cleaning_issue_status == IssueStatus.escalated:
        urgent = True
        reasons.append("Cleaning issue escalated after persistent negative feedback")

    for cluster in repeated_clusters:
        if cluster.category in URGENT_CLUSTER_CATEGORIES:
            urgent = True
            reasons.append(
                f"Repeated {cluster.category.value} complaints "
                f"({cluster.count} from {cluster.distinct_reporters} reporters)"
            )

    if official_score is not None and official_score.value <= settings.SCORE_ATTENTION_MAX:
        high = True
        reasons.append(
            f"Official facility score {official_score.value:.1f} <= attention threshold "
            f"{settings.SCORE_ATTENTION_MAX:.1f}"
        )

    if active_cleaning_issue_status in {
        IssueStatus.open,
        IssueStatus.alert_sent,
        IssueStatus.acknowledged,
    }:
        high = True
        reasons.append(f"Active cleaning alert ({active_cleaning_issue_status.value})")

    for cluster in repeated_clusters:
        if cluster.category not in URGENT_CLUSTER_CATEGORIES:
            high = True
            reasons.append(
                f"Repeated {cluster.category.value} complaints "
                f"({cluster.count} from {cluster.distinct_reporters} reporters)"
            )

    responsibility_unverified = verification_status != VerificationStatus.verified

    if urgent:
        level = TriageLevel.urgent
    elif high:
        level = TriageLevel.high
    elif official_score is not None or has_any_feedback:
        level = TriageLevel.normal
        if inspection_stale:
            reasons.append("Inspection is stale; routine follow-up advised")
        if low_usage:
            reasons.append("Low cleanliness response volume; rely on routine inspection")
        if not reasons:
            reasons.append("Within normal operating thresholds")
    else:
        level = TriageLevel.unranked
        reasons.append("Insufficient information: no official score and no citizen feedback")

    return TriageResult(
        level=level,
        reasons=reasons,
        responsibility_unverified=responsibility_unverified,
        classification_note=CLASSIFICATION_NOTE,
    )
