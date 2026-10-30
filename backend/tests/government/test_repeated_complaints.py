"""Tests for `/api/v1/government/feedback/repeated` repeated-complaint cluster rules."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.modules.government.enums import FeedbackCategory, FeedbackSentiment
from app.modules.government.repositories import RepositoryBundle
from tests.government.factories import (
    FixedClock,
    make_facility,
    make_feedback,
    make_inspection,
)


def test_single_complaint_never_creates_cluster(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    now = fixed_clock.now()
    memory_repos.facilities.seed_facility(make_facility("f-1"))
    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-1",
            "f-1",
            category=FeedbackCategory.water_availability,
            sentiment=FeedbackSentiment.negative,
            reporter_hash="rep-1",
            created_at=now - timedelta(hours=2),
        )
    )

    res = gov_client.get("/api/v1/government/feedback/repeated")
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_three_complaints_from_single_reporter_never_creates_cluster(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    now = fixed_clock.now()
    memory_repos.facilities.seed_facility(make_facility("f-1"))
    for idx in range(3):
        memory_repos.feedback.seed_feedback(
            make_feedback(
                f"fb-{idx}",
                "f-1",
                category=FeedbackCategory.water_availability,
                sentiment=FeedbackSentiment.negative,
                reporter_hash="same-reporter",
                created_at=now - timedelta(hours=idx + 1),
            )
        )

    res = gov_client.get("/api/v1/government/feedback/repeated")
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_three_complaints_from_two_reporters_within_window_creates_cluster(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    now = fixed_clock.now()
    memory_repos.facilities.seed_facility(
        make_facility("f-1", name="MG Road Toilet", ward="Ward-1")
    )

    # 3 negative reviews inside 14-day window from 2 distinct reporters
    for idx, rep in enumerate(["rep-a", "rep-b", "rep-a"], start=1):
        memory_repos.feedback.seed_feedback(
            make_feedback(
                f"fb-in-{idx}",
                "f-1",
                category=FeedbackCategory.broken_equipment,
                sentiment=FeedbackSentiment.negative,
                reporter_hash=rep,
                created_at=now - timedelta(days=idx),
            )
        )

    # 1 negative review outside the 14-day window (must be excluded)
    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-old",
            "f-1",
            category=FeedbackCategory.broken_equipment,
            sentiment=FeedbackSentiment.negative,
            reporter_hash="rep-c",
            created_at=now - timedelta(days=20),
        )
    )

    # Failed evaluator inspections must never be counted in citizen complaint clusters
    for idx in range(5):
        memory_repos.facilities.seed_inspection(
            make_inspection(
                f"insp-{idx}",
                "f-1",
                inspected_at=now - timedelta(days=1),
                checklist_passed=False,
            )
        )

    res = gov_client.get("/api/v1/government/feedback/repeated")
    assert res.status_code == 200
    clusters = res.json()["items"]
    assert len(clusters) == 1
    assert clusters[0]["facility_id"] == "f-1"
    assert clusters[0]["category"] == "broken_equipment"
    assert clusters[0]["count"] == 3
    assert clusters[0]["distinct_reporters"] == 2

