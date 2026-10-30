"""Tests for `/api/v1/government/feedback` and `/api/v1/government/facilities/{id}/feedback`."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.modules.government.domain import CleanlinessWindow
from app.modules.government.enums import (
    CleanlinessVerdict,
    FeedbackCategory,
    FeedbackChannel,
    FeedbackSentiment,
)
from app.modules.government.repositories import RepositoryBundle
from tests.government.factories import FixedClock, make_facility, make_feedback


def test_feedback_filters_age_hours_qr_channel_and_source(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    now = fixed_clock.now()
    memory_repos.facilities.seed_facility(make_facility("f-1", ward="Ward-1"))
    memory_repos.facilities.seed_facility(make_facility("f-2", ward="Ward-2"))

    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-qr-pos",
            "f-1",
            ward="Ward-1",
            category=FeedbackCategory.cleanliness_hygiene,
            sentiment=FeedbackSentiment.positive,
            severity=1,
            channel=FeedbackChannel.qr,
            created_at=now - timedelta(hours=2, minutes=30),
        )
    )
    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-app-neg",
            "f-1",
            ward="Ward-1",
            category=FeedbackCategory.water_availability,
            sentiment=FeedbackSentiment.negative,
            severity=4,
            channel=FeedbackChannel.app,
            linked_issue_id="iss-100",
            created_at=now - timedelta(hours=5),
        )
    )
    memory_repos.feedback.seed_feedback(
        make_feedback(
            "fb-web-neu",
            "f-2",
            ward="Ward-2",
            category=FeedbackCategory.payment_experience,
            sentiment=FeedbackSentiment.neutral,
            severity=2,
            channel=FeedbackChannel.web,
            created_at=now - timedelta(hours=10),
        )
    )

    # Filter by channel=qr
    res_qr = gov_client.get("/api/v1/government/feedback", params={"channel": "qr"})
    assert res_qr.status_code == 200
    qr_items = res_qr.json()["items"]
    assert len(qr_items) == 1
    assert qr_items[0]["id"] == "fb-qr-pos"
    assert qr_items[0]["source"] == "citizen_feedback"
    assert qr_items[0]["age_hours"] == 2.5

    # Filter by linked_to_issue
    res_linked = gov_client.get(
        "/api/v1/government/feedback", params={"linked_to_issue": True}
    )
    assert [i["id"] for i in res_linked.json()["items"]] == ["fb-app-neg"]

    # Filter by sentiment=neutral
    res_neu = gov_client.get(
        "/api/v1/government/feedback", params={"sentiment": "neutral"}
    )
    assert [i["id"] for i in res_neu.json()["items"]] == ["fb-web-neu"]


def test_facility_feedback_includes_sentiment_breakdown_and_window_history_in_meta(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    now = fixed_clock.now()
    memory_repos.facilities.seed_facility(make_facility("f-1"))

    memory_repos.feedback.seed_feedback(
        make_feedback("fb-1", "f-1", sentiment=FeedbackSentiment.positive, created_at=now)
    )
    memory_repos.feedback.seed_feedback(
        make_feedback("fb-2", "f-1", sentiment=FeedbackSentiment.neutral, created_at=now)
    )
    memory_repos.feedback.seed_feedback(
        make_feedback("fb-3", "f-1", sentiment=FeedbackSentiment.negative, created_at=now)
    )
    memory_repos.cleanliness.save_window(
        CleanlinessWindow(
            facility_id="f-1",
            window_start=now - timedelta(hours=1),
            window_end=now,
            yes_count=4,
            no_count=1,
            total=5,
            negative_ratio=0.2,
            verdict=CleanlinessVerdict.clean,
            action="none",
            reasons=["Predominantly positive; no dispatch recommended"],
        )
    )

    res = gov_client.get("/api/v1/government/facilities/f-1/feedback")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert body["meta"]["sentiment_breakdown"] == {
        "positive": 1,
        "neutral": 1,
        "negative": 1,
    }
    assert len(body["meta"]["cleanliness_windows"]) == 1
    assert body["meta"]["cleanliness_windows"][0]["verdict"] == "clean"

