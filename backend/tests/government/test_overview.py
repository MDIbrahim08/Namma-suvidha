"""Tests for `GET /api/v1/government/overview` (`OverviewService`)."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.modules.government.domain import IssueAuditEntry, MaintenanceIssue
from app.modules.government.enums import (
    FeedbackCategory,
    FeedbackSentiment,
    IssueStatus,
    IssueType,
    TriageLevel,
    VerificationStatus,
)
from app.modules.government.providers.scores import IntelligenceScoreProvider
from app.modules.government.repositories import RepositoryBundle
from tests.government.factories import (
    FixedClock,
    make_cleanliness_response,
    make_facility,
    make_feedback,
    make_inspection,
    make_score,
)


def test_overview_empty_returns_all_zeros(
    gov_client: TestClient,
    fixed_clock: FixedClock,
) -> None:
    response = gov_client.get("/api/v1/government/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["data_source"] == "memory"
    zero_fields = [
        "total_facilities",
        "recommended",
        "needing_attention",
        "unscored",
        "unverified",
        "pending_complaints",
        "active_issues",
        "escalated_issues",
        "resolved_issues",
        "recent_inspections",
        "positive_feedback_count",
        "negative_feedback_count",
        "cleanliness_alerts_last_24h",
        "facilities_low_usage",
        "facilities_cleanliness_unknown",
    ]
    for field in zero_fields:
        assert data[field] == 0, f"Expected {field} == 0, got {data[field]}"


def test_overview_populated_counts_and_separates_inspections_from_feedback(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    score_provider: IntelligenceScoreProvider,
) -> None:
    now = fixed_clock.now()

    # 3 facilities:
    # f1: recommended (score 85), verified, 3 cleanliness responses in 24h -> NOT low usage
    # f2: needing_attention (score 35), unverified, 0 responses -> low_usage & cleanliness_unknown
    # f3: unscored (no score), verified, 1 response -> low_usage & cleanliness_unknown
    memory_repos.facilities.seed_facility(
        make_facility("f1", verification_status=VerificationStatus.verified)
    )
    memory_repos.facilities.seed_facility(
        make_facility("f2", verification_status=VerificationStatus.unverified, with_operator=False)
    )
    memory_repos.facilities.seed_facility(
        make_facility("f3", verification_status=VerificationStatus.verified)
    )

    score_provider.register_override("f1", make_score(85.0))
    score_provider.register_override("f2", make_score(35.0))

    # f1 gets 3 responses in last 24h; f3 gets 1; f2 gets 0
    for i in range(3):
        memory_repos.cleanliness.seed_response(
            make_cleanliness_response(
                f"cr-f1-{i}", "f1", is_clean=True, created_at=now - timedelta(hours=1)
            )
        )
    memory_repos.cleanliness.seed_response(
        make_cleanliness_response(
            "cr-f3-1", "f3", is_clean=True, created_at=now - timedelta(hours=2)
        )
    )

    # Inspections: 1 recent (2 days ago), 1 old (20 days ago) — must NEVER count as citizen feedback
    memory_repos.facilities.seed_inspection(
        make_inspection("insp-recent", "f1", inspected_at=now - timedelta(days=2))
    )
    memory_repos.facilities.seed_inspection(
        make_inspection("insp-old", "f2", inspected_at=now - timedelta(days=20))
    )

    # Citizen feedback: 2 positive, 1 unlinked negative (pending), 1 linked negative
    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-pos-1",
            "f1",
            sentiment=FeedbackSentiment.positive,
            created_at=now - timedelta(days=1),
        )
    )
    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-pos-2",
            "f1",
            sentiment=FeedbackSentiment.positive,
            created_at=now - timedelta(days=2),
        )
    )
    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-neg-unlinked",
            "f2",
            sentiment=FeedbackSentiment.negative,
            linked_issue_id=None,
            created_at=now - timedelta(days=3),
        )
    )
    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-neg-linked",
            "f2",
            sentiment=FeedbackSentiment.negative,
            linked_issue_id="iss-1",
            created_at=now - timedelta(days=3),
        )
    )

    # Issues: 1 escalated cleaning alert created 2h ago, 1 resolved maintenance issue
    memory_repos.issues.create(
        MaintenanceIssue(
            id="iss-1",
            type=IssueType.cleaning,
            status=IssueStatus.escalated,
            facility_id="f2",
            ward="Ward-1",
            category=FeedbackCategory.cleanliness_hygiene,
            triage_level=TriageLevel.urgent,
            summary="Cleaning escalated",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=1),
            history=[
                IssueAuditEntry(
                    from_status=None,
                    to_status=IssueStatus.escalated,
                    actor_id="gov-1",
                    note="Escalated",
                    timestamp=now - timedelta(hours=1),
                )
            ],
        )
    )
    memory_repos.issues.create(
        MaintenanceIssue(
            id="iss-2",
            type=IssueType.maintenance,
            status=IssueStatus.resolved,
            facility_id="f1",
            ward="Ward-1",
            category=FeedbackCategory.broken_equipment,
            triage_level=TriageLevel.normal,
            summary="Fixed tap",
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=4),
            history=[],
        )
    )

    response = gov_client.get("/api/v1/government/overview")
    assert response.status_code == 200
    data = response.json()

    assert data["total_facilities"] == 3
    assert data["recommended"] == 1
    assert data["needing_attention"] == 1
    assert data["unscored"] == 1
    assert data["unverified"] == 1
    assert data["pending_complaints"] == 1
    assert data["active_issues"] == 1
    assert data["escalated_issues"] == 1
    assert data["resolved_issues"] == 1
    assert data["recent_inspections"] == 1
    assert data["positive_feedback_count"] == 2
    assert data["negative_feedback_count"] == 2
    assert data["cleanliness_alerts_last_24h"] == 1
    # Both f2 (0 responses) and f3 (1 response) must be counted in low_usage & cleanliness_unknown
    assert data["facilities_low_usage"] == 2
    assert data["facilities_cleanliness_unknown"] == 2

