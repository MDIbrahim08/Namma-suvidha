"""Tests for email notifications, failure handling, acknowledgement, and SMS rejection."""

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import create_app
from app.modules.government.dependencies import (
    get_clock,
    get_email_provider,
)
from app.modules.government.domain import IssueAuditEntry, MaintenanceIssue
from app.modules.government.enums import (
    FeedbackCategory,
    IssueStatus,
    IssueType,
    TriageLevel,
    VerificationStatus,
)
from app.modules.government.providers.email import (
    FailingEmailProvider,
    TestEmailProvider,
)
from app.modules.government.providers.scores import IntelligenceScoreProvider
from app.modules.government.repositories import RepositoryBundle
from tests.government.factories import (
    FixedClock,
    make_facility,
    make_inspection,
    make_score,
)


def _seed_open_issue(
    repos: RepositoryBundle,
    fixed_clock: FixedClock,
    facility_id: str,
    issue_id: str = "iss-1",
) -> MaintenanceIssue:
    now = fixed_clock.now()
    issue = MaintenanceIssue(
        id=issue_id,
        type=IssueType.cleaning,
        status=IssueStatus.open,
        facility_id=facility_id,
        ward="Ward-1",
        category=FeedbackCategory.cleanliness_hygiene,
        triage_level=TriageLevel.high,
        summary="Cleaning alert",
        created_at=now,
        updated_at=now,
        history=[
            IssueAuditEntry(
                from_status=None,
                to_status=IssueStatus.open,
                actor_id="seed",
                note="Created",
                timestamp=now,
            )
        ],
    )
    return repos.issues.create(issue)


def test_notify_without_verified_email_returns_422(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    memory_repos.facilities.seed_facility(
        make_facility(
            "f-unver",
            verification_status=VerificationStatus.unverified,
            operator_email="someone@example.org",
            operator_verified=False,
        )
    )
    _seed_open_issue(memory_repos, fixed_clock, "f-unver", "iss-unver")

    res = gov_client.post("/api/v1/government/issues/iss-unver/notify")
    assert res.status_code == 422
    assert res.json()["code"] == "missing_verified_recipient"


def test_notify_success_resend_acknowledge_and_evidence_id_only_payload(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    score_provider: IntelligenceScoreProvider,
    email_outbox: TestEmailProvider,
) -> None:
    now = fixed_clock.now()
    memory_repos.facilities.seed_facility(
        make_facility("f-ver", operator_email="operator@example.org")
    )
    memory_repos.facilities.seed_inspection(
        make_inspection(
            "insp-10",
            "f-ver",
            inspected_at=now,
            evidence_ids=["photo-id-99"],
        )
    )
    score_provider.register_override("f-ver", make_score(62.0, computed_at=now))
    _seed_open_issue(memory_repos, fixed_clock, "f-ver", "iss-ver")

    # 1. Initial send: open -> alert_sent (NEVER resolved)
    res1 = gov_client.post("/api/v1/government/issues/iss-ver/notify")
    assert res1.status_code == 200
    notif1 = res1.json()
    assert notif1["status"] == "sent"
    assert notif1["recipient"] == "operator@example.org"
    assert notif1["payload"]["evidence_reference_ids"] == ["insp-10", "photo-id-99"]
    # Ensure no storage URLs in evidence_reference_ids
    assert all(
        not ref.startswith("http")
        for ref in notif1["payload"]["evidence_reference_ids"]
    )

    issue = gov_client.get("/api/v1/government/issues/iss-ver").json()
    assert issue["status"] == "alert_sent"

    # 2. Re-sending from alert_sent stays alert_sent and appends an audit note
    fixed_clock.advance(minutes=10)
    res2 = gov_client.post("/api/v1/government/issues/iss-ver/notify")
    assert res2.status_code == 200
    issue_after_resend = gov_client.get("/api/v1/government/issues/iss-ver").json()
    assert issue_after_resend["status"] == "alert_sent"
    assert any("re-sent" in h["note"] for h in issue_after_resend["history"])

    # 3. Acknowledge updates latest notification and transitions issue to acknowledged
    fixed_clock.advance(minutes=5)
    res_ack = gov_client.post(
        "/api/v1/government/issues/iss-ver/transition",
        json={"to_status": "acknowledged", "note": "Team dispatched"},
    )
    assert res_ack.status_code == 200
    acked = res_ack.json()
    assert acked["status"] == "acknowledged"
    assert acked["notifications"][-1]["status"] == "acknowledged"
    assert acked["notifications"][-1]["acknowledged_at"] is not None


def test_failing_email_provider_returns_200_failed_and_keeps_status_open(
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    memory_repos.facilities.seed_facility(
        make_facility("f-ver", operator_email="operator@example.org")
    )
    _seed_open_issue(memory_repos, fixed_clock, "f-ver", "iss-fail")

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "gov-1",
        "roles": ["government"],
    }
    app.dependency_overrides[get_clock] = lambda: fixed_clock
    app.dependency_overrides[get_email_provider] = lambda: FailingEmailProvider(
        "SMTP timeout"
    )

    with TestClient(app) as client:
        res = client.post("/api/v1/government/issues/iss-fail/notify")
        assert res.status_code == 200
        notif = res.json()
        assert notif["status"] == "failed"
        assert notif["provider_message"] == "SMTP timeout"

        issue = client.get("/api/v1/government/issues/iss-fail").json()
        assert issue["status"] == "open"
        assert any("delivery failed" in h["note"] for h in issue["history"])


def test_sms_channel_rejected_as_not_implemented(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    memory_repos.facilities.seed_facility(make_facility("f-1"))
    _seed_open_issue(memory_repos, fixed_clock, "f-1", "iss-sms")

    res = gov_client.post(
        "/api/v1/government/issues/iss-sms/notify", json={"channel": "sms"}
    )
    assert res.status_code == 422
    assert res.json()["code"] == "unsupported_notification_channel"
