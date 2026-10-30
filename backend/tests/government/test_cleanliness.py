"""Tests for feedback-driven cleaning aggregation, verdicts, low-usage, and alerts."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import create_app
from app.modules.government.config import (
    GovernmentSettings,
    get_government_settings,
)
from app.modules.government.dependencies import (
    get_clock,
    get_email_provider,
)
from app.modules.government.domain import EVALUATION_NO_BACKFILL_NOTE
from app.modules.government.enums import VerificationStatus
from app.modules.government.providers.email import TestEmailProvider
from app.modules.government.repositories import RepositoryBundle
from app.modules.government.services.cleanliness import compute_latest_complete_window
from tests.government.factories import (
    FixedClock,
    make_cleanliness_response,
    make_facility,
)


def test_window_alignment_and_zero_response_facility_is_evaluated_never_clean(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    # 12:30 UTC -> latest complete 60m window is [11:00, 12:00)
    fixed_clock.set(datetime(2026, 10, 30, 12, 30, 0, tzinfo=UTC))
    w_start, w_end = compute_latest_complete_window(fixed_clock.now(), 60)
    assert w_start == datetime(2026, 10, 30, 11, 0, 0, tzinfo=UTC)
    assert w_end == datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)

    # Seed a facility with ZERO responses and a facility with 2 responses (< min 3)
    memory_repos.facilities.seed_facility(make_facility("f-zero"))
    memory_repos.facilities.seed_facility(make_facility("f-two"))

    memory_repos.cleanliness.seed_response(
        make_cleanliness_response(
            "cr-1", "f-two", is_clean=True, created_at=w_start + timedelta(minutes=10)
        )
    )
    memory_repos.cleanliness.seed_response(
        make_cleanliness_response(
            "cr-2", "f-two", is_clean=False, created_at=w_start + timedelta(minutes=20)
        )
    )

    res = gov_client.post("/api/v1/government/evaluate")
    assert res.status_code == 200
    clean_summary = res.json()["cleanliness"]

    # Both facilities must be considered and saved as `insufficient_data`, never `clean`
    assert clean_summary["facilities_considered"] == 2
    assert clean_summary["windows_saved"] == 2
    assert clean_summary["insufficient_data"] == 2
    assert clean_summary["clean"] == 0
    assert clean_summary["low_usage_flagged"] == 2
    assert clean_summary["note"] == EVALUATION_NO_BACKFILL_NOTE

    # Check facility detail for zero-response facility
    detail = gov_client.get("/api/v1/government/facilities/f-zero").json()
    assert detail["data_quality"]["low_usage"] is True
    assert detail["data_quality"]["cleanliness_unknown"] is True
    assert detail["latest_cleanliness_window"]["verdict"] == "insufficient_data"
    assert detail["latest_cleanliness_window"]["action"] == "insufficient_data"


def test_clean_vs_needs_cleaning_alert_email_idempotency_escalation_and_reset(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    email_outbox: TestEmailProvider,
) -> None:
    fixed_clock.set(datetime(2026, 10, 30, 12, 30, 0, tzinfo=UTC))
    w1_start, _ = compute_latest_complete_window(fixed_clock.now(), 60)

    # f-pos: 5 YES / 1 NO -> clean, no issue, no email
    # f-neg: 2 YES / 3 NO -> needs_cleaning, alert created, test email sent (`alert_sent`)
    # f-unver: 0 YES / 3 NO, unverified operator -> stays `open`, responsibility_unverified=True
    memory_repos.facilities.seed_facility(
        make_facility("f-pos", operator_email="pos@example.org")
    )
    memory_repos.facilities.seed_facility(
        make_facility("f-neg", operator_email="neg@example.org")
    )
    memory_repos.facilities.seed_facility(
        make_facility(
            "f-unver",
            verification_status=VerificationStatus.unverified,
            operator_email=None,
            operator_verified=False,
        )
    )

    for idx, val in enumerate([True, True, True, True, True, False], start=1):
        memory_repos.cleanliness.seed_response(
            make_cleanliness_response(
                f"pos-{idx}",
                "f-pos",
                is_clean=val,
                created_at=w1_start + timedelta(minutes=idx),
            )
        )
    for idx, val in enumerate([True, True, False, False, False], start=1):
        memory_repos.cleanliness.seed_response(
            make_cleanliness_response(
                f"neg-{idx}",
                "f-neg",
                is_clean=val,
                created_at=w1_start + timedelta(minutes=idx),
            )
        )
    for idx in range(1, 4):
        memory_repos.cleanliness.seed_response(
            make_cleanliness_response(
                f"unv-{idx}",
                "f-unver",
                is_clean=False,
                created_at=w1_start + timedelta(minutes=idx),
            )
        )

    res1 = gov_client.post("/api/v1/government/evaluate")
    assert res1.status_code == 200
    s1 = res1.json()["cleanliness"]
    assert s1["facilities_considered"] == 3
    assert s1["clean"] == 1
    assert s1["needs_cleaning"] == 2
    assert s1["alerts_created"] == 2
    assert s1["alerts_emailed"] == 1
    assert s1["alerts_without_recipient"] == 1
    assert len(email_outbox.outbox) == 1
    assert email_outbox.outbox[0].recipient == "neg@example.org"

    # Re-evaluating the exact same window is idempotent
    res_dup = gov_client.post("/api/v1/government/evaluate")
    s_dup = res_dup.json()["cleanliness"]
    assert s_dup["skipped_existing"] == 3
    assert s_dup["windows_saved"] == 0
    assert s_dup["alerts_created"] == 0
    assert len(email_outbox.outbox) == 1

    # Verify issue statuses after window 1
    issues = gov_client.get("/api/v1/government/issues").json()["items"]
    by_fac = {i["facility_id"]: i for i in issues}
    assert by_fac["f-neg"]["status"] == "alert_sent"
    assert by_fac["f-neg"]["responsibility_unverified"] is False
    assert by_fac["f-unver"]["status"] == "open"
    assert by_fac["f-unver"]["responsibility_unverified"] is True

    # Advance 1 hour to [12:00, 13:00): f-neg is negative again -> escalates
    fixed_clock.advance(hours=1)
    w2_start, _ = compute_latest_complete_window(fixed_clock.now(), 60)
    for idx in range(1, 4):
        memory_repos.cleanliness.seed_response(
            make_cleanliness_response(
                f"neg-w2-{idx}",
                "f-neg",
                is_clean=False,
                created_at=w2_start + timedelta(minutes=idx),
            )
        )

    res2 = gov_client.post("/api/v1/government/evaluate")
    s2 = res2.json()["cleanliness"]
    assert s2["escalations"] == 1

    neg_issue = gov_client.get(
        f"/api/v1/government/issues/{by_fac['f-neg']['id']}"
    ).json()
    assert neg_issue["status"] == "escalated"
    assert neg_issue["verification_requested_at"] is not None
    assert neg_issue["consecutive_negative_windows"] == 1

    # Advance 1 hour to [13:00, 14:00): positive window resets counter without resolving
    fixed_clock.advance(hours=1)
    w3_start, _ = compute_latest_complete_window(fixed_clock.now(), 60)
    for idx in range(1, 5):
        memory_repos.cleanliness.seed_response(
            make_cleanliness_response(
                f"neg-w3-pos-{idx}",
                "f-neg",
                is_clean=True,
                created_at=w3_start + timedelta(minutes=idx),
            )
        )

    gov_client.post("/api/v1/government/evaluate")
    neg_issue_after = gov_client.get(
        f"/api/v1/government/issues/{by_fac['f-neg']['id']}"
    ).json()
    assert neg_issue_after["status"] == "escalated"  # NOT auto-resolved
    assert neg_issue_after["consecutive_negative_windows"] == 0
    assert any(
        "Positive window observed" in h["note"] for h in neg_issue_after["history"]
    )


def test_auto_notify_false_leaves_issue_open_and_skipping_windows_does_not_backfill(
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    email_outbox: TestEmailProvider,
) -> None:
    fixed_clock.set(datetime(2026, 10, 30, 12, 30, 0, tzinfo=UTC))
    memory_repos.facilities.seed_facility(
        make_facility("f-1", operator_email="op@example.org")
    )

    # Seed responses in an earlier missed window [09:00, 10:00) AND latest [11:00, 12:00)
    missed_start = datetime(2026, 10, 30, 9, 0, 0, tzinfo=UTC)
    latest_start = datetime(2026, 10, 30, 11, 0, 0, tzinfo=UTC)
    for idx in range(1, 4):
        memory_repos.cleanliness.seed_response(
            make_cleanliness_response(
                f"missed-{idx}",
                "f-1",
                is_clean=False,
                created_at=missed_start + timedelta(minutes=idx),
            )
        )
        memory_repos.cleanliness.seed_response(
            make_cleanliness_response(
                f"latest-{idx}",
                "f-1",
                is_clean=False,
                created_at=latest_start + timedelta(minutes=idx),
            )
        )

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "gov-1",
        "roles": ["government"],
    }
    app.dependency_overrides[get_clock] = lambda: fixed_clock
    app.dependency_overrides[get_email_provider] = lambda: email_outbox
    app.dependency_overrides[get_government_settings] = lambda: GovernmentSettings(
        CLEAN_AUTO_NOTIFY=False
    )

    with TestClient(app) as client:
        res = client.post("/api/v1/government/evaluate")
        assert res.status_code == 200
        clean = res.json()["cleanliness"]
        assert clean["alerts_created"] == 1
        assert clean["alerts_emailed"] == 0
        assert "not backfilled" in clean["note"]

        # Only 1 window saved (for latest_start), missed window was NOT backfilled
        windows = client.get("/api/v1/government/cleanliness/windows").json()["items"]
        assert len(windows) == 1
        assert windows[0]["window_start"].startswith("2026-10-30T11:00:00")

        # Issue remains `open` because CLEAN_AUTO_NOTIFY=False
        issues = client.get("/api/v1/government/issues").json()["items"]
        assert len(issues) == 1
        assert issues[0]["status"] == "open"
        assert len(email_outbox.outbox) == 0
