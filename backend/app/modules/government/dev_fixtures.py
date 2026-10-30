"""Explicit demo fixtures for the hidden dev-only `/_dev/load-fixtures` endpoint.

OWNER: Ibrahim

NEVER loaded at startup. Only loaded when `POST /api/v1/government/_dev/load-fixtures`
is explicitly invoked in `APP_ENV=development` with `GOV_DEV_FIXTURES_ENABLED=true`.
"""

from datetime import datetime, timedelta

from app.modules.discovery.bbmp_loader import load_bbmp_records
from app.modules.government.domain import (
    CitizenFeedbackItem,
    CleanlinessResponse,
    FacilityRecord,
    InspectionSummary,
    OfficialScore,
    ResponsibleParty,
)
from app.modules.government.enums import (
    FeedbackCategory,
    FeedbackChannel,
    FeedbackSentiment,
    VerificationStatus,
)
from app.modules.government.providers.scores import IntelligenceScoreProvider
from app.modules.government.repositories import RepositoryBundle
from app.modules.government.services.cleanliness import compute_latest_complete_window


def load_dev_fixtures(
    repos: RepositoryBundle,
    score_provider: IntelligenceScoreProvider,
    now: datetime,
    window_minutes: int = 60,
) -> dict[str, object]:
    """Populate the in-memory repositories with the 5 canonical jury demo facilities."""
    repos.clear_all()
    score_provider.clear_overrides()

    window_start, _ = compute_latest_complete_window(now, window_minutes)
    mid_window = window_start + timedelta(minutes=15)

    facilities = [
        # 1. Majority NO responses + verified operator email
        FacilityRecord(
            id="fac-majestic-01",
            name="Majestic Bus Stand Public Toilet",
            ward="Gandhinagar",
            address="Kempegowda Bus Station, Bengaluru",
            lat=12.9767,
            lng=77.5713,
            verification_status=VerificationStatus.verified,
            responsible_party=ResponsibleParty(
                name="Ramesh Kumar",
                organization="BBMP West Zone Sanitation",
                role_title="Ward Sanitation Supervisor",
                email="ramesh.sanitation@example.org",
                phone="+91-80-22220001",
                verified=True,
            ),
        ),
        # 2. Majority YES responses + verified operator email
        FacilityRecord(
            id="fac-indiranagar-02",
            name="Indiranagar 100ft Road Namma Toilet",
            ward="Hoysala Nagar",
            address="100 Feet Rd, Indiranagar, Bengaluru",
            lat=12.9784,
            lng=77.6408,
            verification_status=VerificationStatus.verified,
            responsible_party=ResponsibleParty(
                name="Suma Nair",
                organization="BBMP East Zone Sanitation",
                role_title="Facility Nodal Officer",
                email="suma.eastzone@example.org",
                phone="+91-80-22220002",
                verified=True,
            ),
        ),
        # 3. Only two responses (below min_responses=3 -> insufficient_data & low_usage)
        FacilityRecord(
            id="fac-jayanagar-03",
            name="Jayanagar 4th Block Market Toilet",
            ward="Jayanagar",
            address="4th Block Shopping Complex, Bengaluru",
            lat=12.9250,
            lng=77.5838,
            verification_status=VerificationStatus.verified,
            responsible_party=ResponsibleParty(
                name="Kiran Rao",
                organization="BBMP South Zone Sanitation",
                role_title="Zonal Inspector",
                email="kiran.southzone@example.org",
                phone="+91-80-22220003",
                verified=True,
            ),
        ),
        # 4. ZERO responses (must be evaluated -> insufficient_data & low_usage=True, never clean)
        FacilityRecord(
            id="fac-cubbon-04",
            name="Cubbon Park East Gate Public Toilet",
            ward="Sampangiram Nagar",
            address="Kasturba Road, Bengaluru",
            lat=12.9763,
            lng=77.5929,
            verification_status=VerificationStatus.verified,
            responsible_party=ResponsibleParty(
                name="Anita Desai",
                organization="Horticulture & Civic Sanitation Cell",
                role_title="Park Facility Supervisor",
                email="anita.cubbon@example.org",
                phone="+91-80-22220004",
                verified=True,
            ),
        ),
        # 5. Majority NO responses + UNVERIFIED operator
        # (issue stays open with responsibility_unverified=True)
        FacilityRecord(
            id="fac-krpuram-05",
            name="KR Puram Railway Approach Toilet",
            ward="KR Puram",
            address="Old Madras Road, Bengaluru",
            lat=13.0005,
            lng=77.6744,
            verification_status=VerificationStatus.unverified,
            responsible_party=ResponsibleParty(
                name="Unverified Contractor",
                organization="Pending Contractor Assignment",
                email=None,
                phone=None,
                verified=False,
            ),
        ),
    ]

    for fac in facilities:
        repos.facilities.seed_facility(fac)

    # Load real BBMP records into government facilities repository
    bbmp_records = load_bbmp_records()
    for rec in bbmp_records[:50]:  # Seed first 50 facilities from BBMP dataset
        address = rec.road_street or rec.location or "Bengaluru"
        if rec.zone:
            address = f"{address}, {rec.zone} Zone, Bengaluru"
        repos.facilities.seed_facility(
            FacilityRecord(
                id=rec.id,
                name=rec.display_name,
                ward=rec.ward_name or f"Ward {rec.ward_no or 'BBMP'}",
                address=address,
                lat=rec.latitude,
                lng=rec.longitude,
                verification_status=VerificationStatus.verified if rec.aee else VerificationStatus.unverified,
                responsible_party=ResponsibleParty(
                    name=rec.aee or rec.contractor_name or "BBMP Ward Engineer",
                    organization=f"BBMP {rec.zone or 'Sanitation'} Division",
                    role_title="Assistant Executive Engineer (AEE)" if rec.aee else "Sanitation Contractor",
                    email=None,
                    phone=None,
                    verified=bool(rec.aee),
                ),
            )
        )

    # Official intelligence scores (leaving fac-cubbon-04 unscored so
    # `unscored` & `unranked` are demonstrable)
    score_provider.register_override(
        "fac-majestic-01",
        OfficialScore(value=48.0, computed_at=now - timedelta(days=2)),
    )
    score_provider.register_override(
        "fac-indiranagar-02",
        OfficialScore(value=86.0, computed_at=now - timedelta(days=1)),
    )
    score_provider.register_override(
        "fac-jayanagar-03",
        OfficialScore(value=74.0, computed_at=now - timedelta(days=5)),
    )
    score_provider.register_override(
        "fac-krpuram-05",
        OfficialScore(value=52.0, computed_at=now - timedelta(days=10)),
    )

    # Inspections
    repos.facilities.seed_inspection(
        InspectionSummary(
            inspection_id="insp-001",
            facility_id="fac-majestic-01",
            evaluator_id="eval-10",
            inspected_at=now - timedelta(days=3),
            checklist_passed=False,
            summary_note="Wet floor and soap dispenser empty",
            evidence_ids=["ev-photo-101"],
        )
    )
    repos.facilities.seed_inspection(
        InspectionSummary(
            inspection_id="insp-002",
            facility_id="fac-indiranagar-02",
            evaluator_id="eval-11",
            inspected_at=now - timedelta(days=1),
            checklist_passed=True,
            summary_note="Clean and well-stocked",
            evidence_ids=["ev-photo-102"],
        )
    )
    repos.facilities.seed_inspection(
        InspectionSummary(
            inspection_id="insp-003",
            facility_id="fac-jayanagar-03",
            evaluator_id="eval-12",
            inspected_at=now - timedelta(days=60),  # stale (>45d)
            checklist_passed=True,
            summary_note="Routine inspection passed",
            evidence_ids=["ev-photo-103"],
        )
    )

    # Cleanliness YES/NO responses inside the latest complete window
    # 1. fac-majestic-01: 1 YES, 4 NO -> needs_cleaning + verified operator -> alert_sent
    for idx, is_clean in enumerate([True, False, False, False, False], start=1):
        repos.cleanliness.seed_response(
            CleanlinessResponse(
                id=f"cr-maj-{idx}",
                facility_id="fac-majestic-01",
                is_clean=is_clean,
                channel=FeedbackChannel.qr,
                created_at=mid_window + timedelta(minutes=idx),
                respondent_hash=f"resp-maj-{idx}",
            )
        )

    # 2. fac-indiranagar-02: 5 YES, 1 NO -> clean
    for idx, is_clean in enumerate([True, True, True, True, True, False], start=1):
        repos.cleanliness.seed_response(
            CleanlinessResponse(
                id=f"cr-ind-{idx}",
                facility_id="fac-indiranagar-02",
                is_clean=is_clean,
                channel=FeedbackChannel.qr,
                created_at=mid_window + timedelta(minutes=idx),
                respondent_hash=f"resp-ind-{idx}",
            )
        )

    # 3. fac-jayanagar-03: 2 responses (<3) -> insufficient_data & low_usage
    for idx, is_clean in enumerate([True, False], start=1):
        repos.cleanliness.seed_response(
            CleanlinessResponse(
                id=f"cr-jay-{idx}",
                facility_id="fac-jayanagar-03",
                is_clean=is_clean,
                channel=FeedbackChannel.web,
                created_at=mid_window + timedelta(minutes=idx),
                respondent_hash=f"resp-jay-{idx}",
            )
        )

    # 4. fac-cubbon-04: 0 responses -> insufficient_data & low_usage

    # 5. fac-krpuram-05: 0 YES, 4 NO -> needs_cleaning + unverified operator -> stays open
    for idx in range(1, 5):
        repos.cleanliness.seed_response(
            CleanlinessResponse(
                id=f"cr-krp-{idx}",
                facility_id="fac-krpuram-05",
                is_clean=False,
                channel=FeedbackChannel.qr,
                created_at=mid_window + timedelta(minutes=idx),
                respondent_hash=f"resp-krp-{idx}",
            )
        )

    # Citizen feedback items (positive, neutral, and repeated negative cluster on fac-majestic-01)
    repos.feedback.seed_feedback(
        CitizenFeedbackItem(
            id="fb-001",
            facility_id="fac-indiranagar-02",
            ward="Hoysala Nagar",
            category=FeedbackCategory.overall_satisfaction,
            sentiment=FeedbackSentiment.positive,
            severity=1,
            channel=FeedbackChannel.qr,
            comment="Very clean and well lit.",
            reporter_hash="cit-a",
            created_at=now - timedelta(hours=3),
        )
    )
    repos.feedback.seed_feedback(
        CitizenFeedbackItem(
            id="fb-002",
            facility_id="fac-jayanagar-03",
            ward="Jayanagar",
            category=FeedbackCategory.payment_experience,
            sentiment=FeedbackSentiment.neutral,
            severity=2,
            channel=FeedbackChannel.app,
            comment="UPI QR sticker slightly faded.",
            reporter_hash="cit-b",
            created_at=now - timedelta(hours=12),
        )
    )
    for idx, reporter in enumerate(["cit-1", "cit-2", "cit-1"], start=1):
        repos.feedback.seed_feedback(
            CitizenFeedbackItem(
                id=f"fb-maj-{idx}",
                facility_id="fac-majestic-01",
                ward="Gandhinagar",
                category=FeedbackCategory.water_availability,
                sentiment=FeedbackSentiment.negative,
                severity=4,
                channel=FeedbackChannel.app,
                comment="No running water in taps",
                reporter_hash=reporter,
                evidence_ids=[f"ev-fb-{idx}"],
                created_at=now - timedelta(days=idx),
            )
        )

    return {
        "facilities_loaded": len(facilities),
        "facility_ids": [f.id for f in facilities],
        "window_seeded": window_start.isoformat(),
    }
