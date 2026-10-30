"""Tests for `/api/v1/government/facilities` and `/api/v1/government/facilities/{facility_id}`."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.modules.government.domain import CLASSIFICATION_NOTE
from app.modules.government.enums import VerificationStatus
from app.modules.government.providers.scores import IntelligenceScoreProvider
from app.modules.government.repositories import RepositoryBundle
from tests.government.factories import (
    FixedClock,
    make_cleanliness_response,
    make_facility,
    make_inspection,
    make_score,
)


def test_list_facilities_filters_by_ward_verification_condition_and_radius(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    score_provider: IntelligenceScoreProvider,
) -> None:
    now = fixed_clock.now()

    memory_repos.facilities.seed_facility(
        make_facility(
            "f-rec",
            ward="Ward-A",
            lat=12.9750,
            lng=77.6050,
            verification_status=VerificationStatus.verified,
        )
    )
    memory_repos.facilities.seed_facility(
        make_facility(
            "f-att",
            ward="Ward-B",
            lat=12.9760,
            lng=77.6060,
            verification_status=VerificationStatus.unverified,
            with_operator=False,
        )
    )
    memory_repos.facilities.seed_facility(
        make_facility(
            "f-unscored",
            ward="Ward-A",
            lat=13.1000,
            lng=77.7000,
            verification_status=VerificationStatus.verified,
        )
    )

    score_provider.register_override("f-rec", make_score(82.0, computed_at=now))
    score_provider.register_override("f-att", make_score(30.0, computed_at=now))
    # f-unscored has no score -> condition must be `unscored` (never treated as poor)

    # Filter by ward
    res = gov_client.get("/api/v1/government/facilities", params={"ward": "Ward-A"})
    assert res.status_code == 200
    ids = [item["id"] for item in res.json()["items"]]
    assert ids == ["f-rec", "f-unscored"]

    # Filter by verification_status
    res = gov_client.get(
        "/api/v1/government/facilities", params={"verification_status": "unverified"}
    )
    assert [item["id"] for item in res.json()["items"]] == ["f-att"]

    # Filter by condition bands including unscored
    res_unscored = gov_client.get(
        "/api/v1/government/facilities", params={"condition": "unscored"}
    )
    assert [item["id"] for item in res_unscored.json()["items"]] == ["f-unscored"]

    res_rec = gov_client.get(
        "/api/v1/government/facilities", params={"condition": "recommended"}
    )
    assert [item["id"] for item in res_rec.json()["items"]] == ["f-rec"]

    # Filter by radius (haversine): 500m around (12.9750, 77.6050)
    res_geo = gov_client.get(
        "/api/v1/government/facilities",
        params={"lat": 12.9750, "lng": 77.6050, "radius_m": 500},
    )
    assert [item["id"] for item in res_geo.json()["items"]] == ["f-att", "f-rec"]


def test_list_facilities_stale_only_and_low_usage_only(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
) -> None:
    now = fixed_clock.now()
    memory_repos.facilities.seed_facility(make_facility("f-stale"))
    memory_repos.facilities.seed_facility(make_facility("f-fresh"))
    memory_repos.facilities.seed_facility(make_facility("f-never"))

    memory_repos.facilities.seed_inspection(
        make_inspection("i-stale", "f-stale", inspected_at=now - timedelta(days=50))
    )
    memory_repos.facilities.seed_inspection(
        make_inspection("i-fresh", "f-fresh", inspected_at=now - timedelta(days=5))
    )

    # Give f-fresh 3 cleanliness responses so it is NOT low usage
    for idx in range(3):
        memory_repos.cleanliness.seed_response(
            make_cleanliness_response(
                f"cr-{idx}", "f-fresh", is_clean=True, created_at=now - timedelta(hours=1)
            )
        )

    res_stale = gov_client.get(
        "/api/v1/government/facilities", params={"stale_only": True}
    )
    assert [item["id"] for item in res_stale.json()["items"]] == ["f-stale"]

    res_low = gov_client.get(
        "/api/v1/government/facilities", params={"low_usage_only": True}
    )
    low_ids = [item["id"] for item in res_low.json()["items"]]
    assert low_ids == ["f-never", "f-stale"]


def test_facility_detail_flags_responsible_party_and_404(
    gov_client: TestClient,
    fixed_clock: FixedClock,
    memory_repos: RepositoryBundle,
    score_provider: IntelligenceScoreProvider,
) -> None:
    now = fixed_clock.now()

    memory_repos.facilities.seed_facility(
        make_facility(
            "f-verified",
            verification_status=VerificationStatus.verified,
            operator_email="verified@example.org",
            operator_verified=True,
        )
    )
    memory_repos.facilities.seed_facility(
        make_facility(
            "f-unverified",
            verification_status=VerificationStatus.unverified,
            operator_email="unverified@example.org",
            operator_verified=False,
        )
    )
    score_provider.register_override("f-verified", make_score(78.0, computed_at=now))

    # Verified facility returns responsible_party with contact fields for government viewer
    res_v = gov_client.get("/api/v1/government/facilities/f-verified")
    assert res_v.status_code == 200
    body_v = res_v.json()
    assert body_v["responsible_party"]["email"] == "verified@example.org"
    assert body_v["data_quality"]["never_inspected"] is True
    assert body_v["data_quality"]["missing_operator"] is False
    assert body_v["data_quality"]["low_usage"] is True
    assert body_v["data_quality"]["cleanliness_unknown"] is True
    assert body_v["triage"]["classification_note"] == CLASSIFICATION_NOTE

    # Unverified facility omits responsible_party and sets missing_operator=True
    res_u = gov_client.get("/api/v1/government/facilities/f-unverified")
    assert res_u.status_code == 200
    body_u = res_u.json()
    assert body_u["responsible_party"] is None
    assert body_u["data_quality"]["missing_operator"] is True
    assert body_u["triage"]["responsibility_unverified"] is True

    # Unknown facility -> 404
    res_404 = gov_client.get("/api/v1/government/facilities/does-not-exist")
    assert res_404.status_code == 404
    assert res_404.json()["code"] == "http_404"
