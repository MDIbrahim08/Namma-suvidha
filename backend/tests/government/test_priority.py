"""Tests for Government triage classification (`priority.py`) and facility detail."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.modules.government.domain import (
    CLASSIFICATION_NOTE,
    IssueAuditEntry,
    MaintenanceIssue,
)
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
    make_facility,
    make_feedback,
    make_score,
)


def test_no_score_and_no_feedback_is_unranked_and_low_usage_never_escalates(
    gov_client: TestClient,
    memory_repos: RepositoryBundle,
) -> None:
    memory_repos.facilities.seed_facility(make_facility("f-empty"))

    res = gov_client.get("/api/v1/government/facilities/f-empty")
    assert res.status_code == 200
    body = res.json()
    assert body["data_quality"]["low_usage"] is True
    assert body["triage"]["level"] == "unranked"
    assert body["triage"]["classification_note"] == CLASSIFICATION_NOTE


def test_single_negative_review_never_yields_urgent_or_high(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    now = fixed_clock.now()
    memory_repos.facilities.seed_facility(make_facility("f-single"))
    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-1",
            "f-single",
            category=FeedbackCategory.safety,
            sentiment=FeedbackSentiment.negative,
            severity=5,
            reporter_hash="rep-1",
            created_at=now - timedelta(hours=1),
        )
    )

    res = gov_client.get("/api/v1/government/facilities/f-single")
    assert res.status_code == 200
    triage = res.json()["triage"]
    assert triage["level"] == "normal"
    assert triage["classification_note"] == CLASSIFICATION_NOTE


def test_each_triage_rule_fires_with_reason_and_unverified_flag_does_not_alter_level(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    score_provider: IntelligenceScoreProvider,
) -> None:
    now = fixed_clock.now()

    # 1. Low official score (<= 40) -> high, unverified sets responsibility_unverified=True
    memory_repos.facilities.seed_facility(
        make_facility(
            "f-low-score",
            verification_status=VerificationStatus.unverified,
            with_operator=False,
        )
    )
    score_provider.register_override("f-low-score", make_score(32.0, computed_at=now))

    res_high = gov_client.get("/api/v1/government/facilities/f-low-score").json()
    assert res_high["triage"]["level"] == "high"
    assert res_high["triage"]["responsibility_unverified"] is True
    assert any("Official facility score" in r for r in res_high["triage"]["reasons"])

    # 2. Repeated cluster in locked_facility -> urgent
    memory_repos.facilities.seed_facility(make_facility("f-locked"))
    for idx, rep in enumerate(["u1", "u2", "u1"], start=1):
        memory_repos.feedback.seed_feedback(
            make_feedback(
                f"fb-l-{idx}",
                "f-locked",
                category=FeedbackCategory.locked_facility,
                sentiment=FeedbackSentiment.negative,
                reporter_hash=rep,
                created_at=now - timedelta(hours=idx),
            )
        )
    res_urg = gov_client.get("/api/v1/government/facilities/f-locked").json()
    assert res_urg["triage"]["level"] == "urgent"
    assert any(
        "Repeated locked_facility complaints" in r for r in res_urg["triage"]["reasons"]
    )

    # 3. Escalated cleaning issue -> urgent
    memory_repos.facilities.seed_facility(make_facility("f-esc"))
    memory_repos.issues.create(
        MaintenanceIssue(
            id="iss-esc",
            type=IssueType.cleaning,
            status=IssueStatus.escalated,
            facility_id="f-esc",
            ward="Ward-1",
            category=FeedbackCategory.cleanliness_hygiene,
            triage_level=TriageLevel.urgent,
            summary="Escalated",
            created_at=now,
            updated_at=now,
            history=[
                IssueAuditEntry(
                    from_status=None,
                    to_status=IssueStatus.escalated,
                    actor_id="sys",
                    note="Escalated",
                    timestamp=now,
                )
            ],
        )
    )
    res_esc = gov_client.get("/api/v1/government/facilities/f-esc").json()
    assert res_esc["triage"]["level"] == "urgent"
    assert any("escalated" in r.lower() for r in res_esc["triage"]["reasons"])
