"""Tests for issue lifecycle, transitions, note requirements, and maintenance detection."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.modules.government.domain import IssueAuditEntry, MaintenanceIssue
from app.modules.government.enums import (
    FeedbackCategory,
    FeedbackSentiment,
    IssueStatus,
    IssueType,
    TriageLevel,
)
from app.modules.government.providers.scores import IntelligenceScoreProvider
from app.modules.government.repositories import RepositoryBundle
from app.modules.government.services.issues import ALLOWED_ISSUE_TRANSITIONS
from tests.government.factories import (
    FixedClock,
    make_facility,
    make_feedback,
    make_score,
)


def _seed_issue_with_status(
    repos: RepositoryBundle,
    fixed_clock: FixedClock,
    status: IssueStatus,
    issue_id: str = "iss-test",
) -> MaintenanceIssue:
    now = fixed_clock.now()
    repos.facilities.seed_facility(make_facility("f-1"))
    issue = MaintenanceIssue(
        id=issue_id,
        type=IssueType.cleaning,
        status=status,
        facility_id="f-1",
        ward="Ward-1",
        category=FeedbackCategory.cleanliness_hygiene,
        triage_level=TriageLevel.high,
        summary="Test issue",
        created_at=now,
        updated_at=now,
        history=[
            IssueAuditEntry(
                from_status=None,
                to_status=status,
                actor_id="seed",
                note="Initial seed status",
                timestamp=now,
            )
        ],
    )
    return repos.issues.create(issue)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (from_s, to_s)
        for from_s, targets in ALLOWED_ISSUE_TRANSITIONS.items()
        for to_s in targets
    ],
)
def test_every_legal_transition_succeeds_and_appends_history(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    from_status: IssueStatus,
    to_status: IssueStatus,
) -> None:
    _seed_issue_with_status(memory_repos, fixed_clock, from_status, "iss-legal")
    fixed_clock.advance(minutes=5)

    res = gov_client.post(
        "/api/v1/government/issues/iss-legal/transition",
        json={"to_status": to_status.value, "note": "Valid transition note"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == to_status.value
    assert len(body["history"]) == 2
    assert body["history"][-1]["from_status"] == from_status.value
    assert body["history"][-1]["to_status"] == to_status.value
    assert body["history"][-1]["actor_id"] == "gov-officer-1"
    assert body["history"][-1]["note"] == "Valid transition note"


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (from_s, to_s)
        for from_s, targets in ALLOWED_ISSUE_TRANSITIONS.items()
        for to_s in IssueStatus
        if to_s not in targets
    ],
)
def test_every_illegal_transition_returns_409(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    from_status: IssueStatus,
    to_status: IssueStatus,
) -> None:
    _seed_issue_with_status(memory_repos, fixed_clock, from_status, "iss-illegal")

    res = gov_client.post(
        "/api/v1/government/issues/iss-illegal/transition",
        json={"to_status": to_status.value, "note": "Attempted illegal transition"},
    )
    assert res.status_code == 409
    assert res.json()["code"] == "illegal_issue_transition"
    assert f"{from_status.value} -> {to_status.value}" in res.json()["detail"]


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (IssueStatus.acknowledged, IssueStatus.resolved),
        (IssueStatus.open, IssueStatus.dismissed),
    ],
)
def test_resolve_and_dismiss_require_non_empty_note(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    from_status: IssueStatus,
    to_status: IssueStatus,
) -> None:
    _seed_issue_with_status(memory_repos, fixed_clock, from_status, "iss-note")

    res = gov_client.post(
        "/api/v1/government/issues/iss-note/transition",
        json={"to_status": to_status.value, "note": "   "},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "transition_note_required"


def test_maintenance_detection_creates_issues_and_skips_duplicates(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    score_provider: IntelligenceScoreProvider,
) -> None:
    now = fixed_clock.now()
    memory_repos.facilities.seed_facility(make_facility("f-maint"))
    score_provider.register_override("f-maint", make_score(30.0, computed_at=now))

    # Add a qualifying repeated complaint cluster in safety -> urgent triage
    for idx, rep in enumerate(["r1", "r2", "r1"], start=1):
        memory_repos.feedback.seed_feedback(
            make_feedback(
                f"fb-s-{idx}",
                "f-maint",
                category=FeedbackCategory.safety,
                sentiment=FeedbackSentiment.negative,
                reporter_hash=rep,
                created_at=now - timedelta(hours=idx),
            )
        )

    res1 = gov_client.post("/api/v1/government/evaluate")
    assert res1.status_code == 200
    maint1 = res1.json()["maintenance"]
    assert maint1["issues_created"] == 1
    assert maint1["existing_issues_noted"] == 0

    # Calling evaluate again does not duplicate the open maintenance issue; appends a note instead
    res2 = gov_client.post("/api/v1/government/evaluate")
    maint2 = res2.json()["maintenance"]
    assert maint2["issues_created"] == 0
    assert maint2["existing_issues_noted"] == 1

    issues = gov_client.get(
        "/api/v1/government/issues", params={"type": "maintenance"}
    ).json()["items"]
    assert len(issues) == 1
    assert issues[0]["triage_level"] == "urgent"
    assert len(issues[0]["history"]) == 2
