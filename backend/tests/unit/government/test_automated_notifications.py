"""Unit and integration tests for the Automated Government Notification Backend.

OWNER: Ibrahim / Government Automated Notification System

Verifies:
1. Contact resolution from configuration (ward-to-authority mapping).
2. Structured 11-point incident report generation.
3. Notification dispatch to configured test recipients.
4. Truthful delivery tracking (sent vs failed).
5. Duplicate alert suppression for unresolved incidents.
6. Automated escalation when response deadline is missed.
7. Backend audit logging for incidents, notifications, and resolutions.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.government.config import GovernmentSettings
from app.modules.government.contacts import OfficialContact, OfficialContactDirectory
from app.modules.government.domain import (
    CitizenFeedbackItem,
    FacilityRecord,
    InspectionSummary,
    MaintenanceIssue,
    OfficialScore,
    ResponsibleParty,
)
from app.modules.government.enums import (
    FeedbackCategory,
    FeedbackChannel,
    FeedbackSentiment,
    IssueStatus,
    IssueType,
    NotificationChannel,
    NotificationStatus,
    TriageLevel,
    VerificationStatus,
)
from app.modules.government.providers.email import FailingEmailProvider, TestEmailProvider
from app.modules.government.providers.scores import IntelligenceScoreProvider
from app.modules.government.repositories.memory import (
    InMemoryCleanlinessRepository,
    InMemoryFacilityRepository,
    InMemoryFeedbackRepository,
    InMemoryIssueRepository,
)
from app.modules.government.services.issues import IssueService
from app.modules.government.services.notifications import NotificationService


@pytest.fixture
def test_now() -> datetime:
    return datetime(2026, 10, 31, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def facility_repo() -> InMemoryFacilityRepository:
    repo = InMemoryFacilityRepository()
    # Facility in Gandhinagar ward
    repo.save(
        FacilityRecord(
            id="fac-majestic-01",
            name="Majestic Bus Stand Subway Washroom",
            ward="Gandhinagar",
            address="Subhash Nagar, Gandhinagar, Bengaluru",
            lat=12.9767,
            lng=77.5713,
            verification_status=VerificationStatus.verified,
            responsible_party=ResponsibleParty(
                name="Ramesh Kumar",
                organization="BBMP West Zone",
                role_title="Sanitation Supervisor",
                email="bbmp.west.sanitation.test@example.org",
                phone="+91-80-22220001",
                verified=True,
            ),
        )
    )
    # Facility in Electronic City without direct responsible party (must resolve via directory)
    repo.save(
        FacilityRecord(
            id="fac-ecity-02",
            name="Electronic City Toll Gate Namma Toilet",
            ward="Electronic City",
            address="Hosur Road, Electronic City Phase 1",
            lat=12.8398,
            lng=77.6775,
            verification_status=VerificationStatus.unverified,
            responsible_party=None,
        )
    )
    return repo


@pytest.fixture
def issue_repo() -> InMemoryIssueRepository:
    return InMemoryIssueRepository()


@pytest.fixture
def feedback_repo(facility_repo: InMemoryFacilityRepository) -> InMemoryFeedbackRepository:
    repo = InMemoryFeedbackRepository(facility_repo=facility_repo)
    # Add feedback items
    repo.save(
        CitizenFeedbackItem(
            id="fb-01",
            facility_id="fac-majestic-01",
            ward="Gandhinagar",
            category=FeedbackCategory.cleanliness_hygiene,
            sentiment=FeedbackSentiment.negative,
            severity=5,
            channel=FeedbackChannel.app,
            comment="Severe ammonia odour, overflow in urinal, wet soiled floors.",
            created_at=datetime(2026, 10, 31, 9, 30, 0, tzinfo=UTC),
        )
    )
    repo.save(
        CitizenFeedbackItem(
            id="fb-02",
            facility_id="fac-majestic-01",
            ward="Gandhinagar",
            category=FeedbackCategory.cleanliness_hygiene,
            sentiment=FeedbackSentiment.negative,
            severity=4,
            channel=FeedbackChannel.app,
            comment="Handwash dispenser broken and no running water in washbasins.",
            created_at=datetime(2026, 10, 31, 9, 45, 0, tzinfo=UTC),
        )
    )
    return repo


@pytest.fixture
def notification_bundle(
    facility_repo: InMemoryFacilityRepository,
    issue_repo: InMemoryIssueRepository,
    feedback_repo: InMemoryFeedbackRepository,
):
    cleanliness_repo = InMemoryCleanlinessRepository()
    score_provider = IntelligenceScoreProvider()
    email_provider = TestEmailProvider()
    settings = GovernmentSettings()

    issue_service = IssueService(
        issue_repo=issue_repo,
        facility_repo=facility_repo,
        feedback_repo=feedback_repo,
        cleanliness_repo=cleanliness_repo,
        score_provider=score_provider,
        settings=settings,
    )

    contact_dir = OfficialContactDirectory()

    notif_service = NotificationService(
        issue_repo=issue_repo,
        facility_repo=facility_repo,
        feedback_repo=feedback_repo,
        cleanliness_repo=cleanliness_repo,
        score_provider=score_provider,
        email_provider=email_provider,
        issue_service=issue_service,
        settings=settings,
        contacts_directory=contact_dir,
    )

    return {
        "notifications": notif_service,
        "issues": issue_service,
        "email": email_provider,
        "contacts": contact_dir,
        "issue_repo": issue_repo,
        "facility_repo": facility_repo,
    }


def test_contact_directory_resolution():
    dir = OfficialContactDirectory()
    # Resolve Gandhinagar ward
    c1 = dir.resolve_contact("Gandhinagar")
    assert c1 is not None
    assert "bbmp.west" in c1.official_email
    assert c1.active is True

    # Resolve Bommanahalli / Electronic City
    c2 = dir.resolve_contact("Electronic City")
    assert c2 is not None
    assert "bbmp.bommanahalli" in c2.official_email

    # Resolve Escalation Supervisor
    c_esc = dir.resolve_contact("Any Ward", for_escalation=True)
    assert c_esc is not None
    assert c_esc.is_escalation_supervisor is True
    assert "chief.escalations" in c_esc.official_email


def test_structured_incident_report_generation(notification_bundle, test_now):
    svc: NotificationService = notification_bundle["notifications"]
    issue_svc: IssueService = notification_bundle["issues"]

    # Create an urgent maintenance issue
    issue = issue_svc.create_issue(
        issue_type=IssueType.cleaning,
        facility_id="fac-majestic-01",
        ward="Gandhinagar",
        category=FeedbackCategory.cleanliness_hygiene,
        triage_level=TriageLevel.urgent,
        summary="Critical sanitation failure with 2 severe citizen reports",
        responsibility_unverified=False,
        consecutive_negative_windows=1,
        actor_id="system-test",
        initial_note="Automated triage trigger",
        now=test_now,
    )

    report = svc.generate_incident_report(issue, test_now)

    assert report.incident_id.startswith("INC-")
    assert report.toilet_name == "Majestic Bus Stand Subway Washroom"
    assert report.toilet_id == "fac-majestic-01"
    assert report.issue_category == "cleanliness_hygiene"
    assert report.related_complaints_count == 2
    assert report.severity == 5
    assert report.priority == "urgent"
    assert "ammonia odour" in report.citizen_feedback_summary
    assert "within 2h" in report.recommended_maintenance_action
    # Urgent deadline is 2 hours from detection
    assert report.response_deadline == test_now + timedelta(hours=2)
    assert report.is_overdue is False


def test_send_alert_and_delivery_tracking(notification_bundle, test_now):
    svc: NotificationService = notification_bundle["notifications"]
    issue_svc: IssueService = notification_bundle["issues"]
    email: TestEmailProvider = notification_bundle["email"]

    issue = issue_svc.create_issue(
        issue_type=IssueType.cleaning,
        facility_id="fac-majestic-01",
        ward="Gandhinagar",
        category=FeedbackCategory.cleanliness_hygiene,
        triage_level=TriageLevel.urgent,
        summary="Urgent cleaning required",
        responsibility_unverified=False,
        consecutive_negative_windows=1,
        actor_id="system-test",
        initial_note="Test trigger",
        now=test_now,
    )

    notif = svc.send_alert(issue.id, actor_id="admin-test", now=test_now)

    assert notif.status == NotificationStatus.sent
    assert notif.recipient == "bbmp.west.sanitation.test@example.org"
    assert len(email.outbox) == 1
    sent_msg = email.outbox[0]
    assert sent_msg.recipient == "bbmp.west.sanitation.test@example.org"
    assert "INC-" in sent_msg.subject
    assert "GOVERNMENT SANITATION INCIDENT REPORT" in sent_msg.body
    assert "Response Deadline" in sent_msg.body

    # Check that issue transitioned to alert_sent
    updated_issue = notification_bundle["issue_repo"].get(issue.id)
    assert updated_issue.status == IssueStatus.alert_sent

    # Verify backend audit trail was recorded
    audit_records = svc.list_audit_records(event_type="notification_generation")
    assert len(audit_records) == 1
    assert audit_records[0].delivery_status == "sent"
    assert audit_records[0].recipient == "bbmp.west.sanitation.test@example.org"


def test_duplicate_alert_prevention(notification_bundle, test_now):
    svc: NotificationService = notification_bundle["notifications"]
    issue_svc: IssueService = notification_bundle["issues"]
    email: TestEmailProvider = notification_bundle["email"]

    issue = issue_svc.create_issue(
        issue_type=IssueType.cleaning,
        facility_id="fac-majestic-01",
        ward="Gandhinagar",
        category=FeedbackCategory.cleanliness_hygiene,
        triage_level=TriageLevel.high,
        summary="High priority issue",
        responsibility_unverified=False,
        consecutive_negative_windows=1,
        actor_id="system-test",
        initial_note="Initial test",
        now=test_now,
    )

    # First send
    notif1 = svc.send_alert(issue.id, actor_id="admin-test", now=test_now)
    assert notif1.status == NotificationStatus.sent
    assert len(email.outbox) == 1

    # Second send for the same unresolved issue without force_resend -> MUST BE SUPPRESSED
    notif2 = svc.send_alert(issue.id, actor_id="admin-test", now=test_now + timedelta(minutes=10))
    assert notif2.id == notif1.id
    # Outbox count should still be 1 (no duplicate sent)
    assert len(email.outbox) == 1


def test_failing_provider_delivery_status(notification_bundle, test_now):
    # Test that failure is truthfully logged and not faked as sent
    issue_svc: IssueService = notification_bundle["issues"]
    failing_email = FailingEmailProvider(reason="SMTP 550 Mailbox unavailable")

    failing_svc = NotificationService(
        issue_repo=notification_bundle["issue_repo"],
        facility_repo=notification_bundle["facility_repo"],
        feedback_repo=notification_bundle["notifications"]._feedback,
        cleanliness_repo=notification_bundle["notifications"]._cleanliness,
        score_provider=notification_bundle["notifications"]._scores,
        email_provider=failing_email,
        issue_service=issue_svc,
        settings=GovernmentSettings(),
        contacts_directory=notification_bundle["contacts"],
    )

    issue = issue_svc.create_issue(
        issue_type=IssueType.maintenance,
        facility_id="fac-majestic-01",
        ward="Gandhinagar",
        category=FeedbackCategory.broken_equipment,
        triage_level=TriageLevel.normal,
        summary="Tap leaking continuously",
        responsibility_unverified=False,
        consecutive_negative_windows=0,
        actor_id="system-test",
        initial_note="Test trigger",
        now=test_now,
    )

    notif = failing_svc.send_alert(issue.id, actor_id="admin-test", now=test_now)
    assert notif.status == NotificationStatus.failed
    assert "SMTP 550" in notif.provider_message

    audit = failing_svc.list_audit_records(event_type="notification_generation")
    assert len(audit) == 1
    assert audit[0].delivery_status == "failed"


def test_automated_escalation_on_deadline_missed(notification_bundle, test_now):
    svc: NotificationService = notification_bundle["notifications"]
    issue_svc: IssueService = notification_bundle["issues"]
    email: TestEmailProvider = notification_bundle["email"]

    # Create an urgent issue (deadline: 2 hours)
    issue = issue_svc.create_issue(
        issue_type=IssueType.cleaning,
        facility_id="fac-majestic-01",
        ward="Gandhinagar",
        category=FeedbackCategory.cleanliness_hygiene,
        triage_level=TriageLevel.urgent,
        summary="Urgent sanitation issue",
        responsibility_unverified=False,
        consecutive_negative_windows=1,
        actor_id="system-test",
        initial_note="Initial alert",
        now=test_now,
    )
    svc.send_alert(issue.id, actor_id="admin-test", now=test_now)
    email.clear()

    # Time moves forward 3 hours (deadline was +2 hours -> NOW MISSED)
    later_time = test_now + timedelta(hours=3)

    escalations = svc.check_and_escalate_overdue_issues(now=later_time)
    assert len(escalations) == 1
    esc_record = escalations[0]

    assert esc_record.status == NotificationStatus.sent
    assert "chief.escalations" in esc_record.recipient
    assert len(email.outbox) == 1
    sent_esc = email.outbox[0]
    assert "[ESCALATION - OVERDUE]" in sent_esc.subject
    assert "EXPIRED" in sent_esc.body

    # Check issue transitioned to escalated
    updated_issue = notification_bundle["issue_repo"].get(issue.id)
    assert updated_issue.status == IssueStatus.escalated

    # Verify audit log recorded escalation_event
    audit = svc.list_audit_records(event_type="escalation_event")
    assert len(audit) == 1
    assert audit[0].delivery_status == "sent"
    assert "chief.escalations" in audit[0].recipient


def test_acknowledgement_and_resolution_flow(notification_bundle, test_now):
    svc: NotificationService = notification_bundle["notifications"]
    issue_svc: IssueService = notification_bundle["issues"]

    issue = issue_svc.create_issue(
        issue_type=IssueType.cleaning,
        facility_id="fac-majestic-01",
        ward="Gandhinagar",
        category=FeedbackCategory.cleanliness_hygiene,
        triage_level=TriageLevel.high,
        summary="Soap and water issue",
        responsibility_unverified=False,
        consecutive_negative_windows=1,
        actor_id="system-test",
        initial_note="Initial alert",
        now=test_now,
    )
    svc.send_alert(issue.id, actor_id="admin-test", now=test_now)

    # Acknowledge
    ack_time = test_now + timedelta(minutes=20)
    ack_issue = svc.acknowledge(
        issue.id,
        actor_id="supervisor-ramesh",
        note="Acknowledged. Cleaning team dispatched.",
        now=ack_time,
    )
    assert ack_issue.status == IssueStatus.acknowledged

    # Resolve
    resolve_time = test_now + timedelta(minutes=45)
    res_issue = svc.resolve(
        issue.id,
        actor_id="supervisor-ramesh",
        note="Washroom cleaned, pans sanitized, soap dispenser refilled.",
        now=resolve_time,
    )
    assert res_issue.status == IssueStatus.resolved

    # Audit records reflect status transition and resolution
    audits = svc.list_audit_records()
    event_types = [a.event_type for a in audits]
    assert "status_transition" in event_types
    assert "maintenance_resolution" in event_types

