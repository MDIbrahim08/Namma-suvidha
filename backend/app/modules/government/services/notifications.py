"""Email notification orchestration and delivery tracking.

OWNER: Ibrahim

Sending an alert NEVER auto-resolves an issue. Failures never raise; the service
records `NotificationStatus.failed` with the provider message and returns the
`NotificationRecord`.
"""

import uuid
from datetime import datetime
from typing import Any

from app.modules.government.config import GovernmentSettings
from app.modules.government.domain import (
    CLASSIFICATION_NOTE,
    IssueAuditEntry,
    MaintenanceIssue,
    NotificationRecord,
)
from app.modules.government.enums import (
    IssueStatus,
    NotificationChannel,
    NotificationStatus,
    VerificationStatus,
)
from app.modules.government.exceptions import (
    MissingVerifiedRecipientError,
    ResourceNotFoundError,
    UnsupportedNotificationChannelError,
)
from app.modules.government.interfaces import (
    CleanlinessRepository,
    EmailProvider,
    FacilityRepository,
    FacilityScoreProvider,
    FeedbackRepository,
    IssueRepository,
)
from app.modules.government.services.issues import IssueService


class NotificationService:
    def __init__(
        self,
        issue_repo: IssueRepository,
        facility_repo: FacilityRepository,
        feedback_repo: FeedbackRepository,
        cleanliness_repo: CleanlinessRepository,
        score_provider: FacilityScoreProvider,
        email_provider: EmailProvider,
        issue_service: IssueService,
        settings: GovernmentSettings,
    ) -> None:
        self._issues = issue_repo
        self._facilities = facility_repo
        self._feedback = feedback_repo
        self._cleanliness = cleanliness_repo
        self._scores = score_provider
        self._email = email_provider
        self._issue_service = issue_service
        self._settings = settings

    def send_alert(
        self,
        issue_id: str,
        *,
        actor_id: str,
        now: datetime,
        channel: NotificationChannel = NotificationChannel.email,
    ) -> NotificationRecord:
        if channel != NotificationChannel.email:
            raise UnsupportedNotificationChannelError(
                f"Notification channel '{channel.value}' is reserved and "
                "not implemented in Phase 2."
            )

        issue = self._issues.get(issue_id)
        if issue is None:
            raise ResourceNotFoundError(f"Issue '{issue_id}' not found")

        facility = self._facilities.get(issue.facility_id)
        if facility is None:
            raise ResourceNotFoundError(f"Facility '{issue.facility_id}' not found")

        party = facility.responsible_party
        if (
            facility.verification_status != VerificationStatus.verified
            or party is None
            or not party.verified
            or not party.email
        ):
            raise MissingVerifiedRecipientError(
                "No verified email recipient configured for this facility."
            )

        latest_window = self._cleanliness.latest_window(facility.id)
        official_score = self._scores.get_score(facility.id)
        latest_insp = self._facilities.latest_inspection(facility.id)
        feedback_items = self._feedback.list_for_facility(facility.id)

        evidence_ids: list[str] = []
        if latest_insp:
            evidence_ids.append(latest_insp.inspection_id)
            evidence_ids.extend(latest_insp.evidence_ids)
        for fb in feedback_items[:5]:
            evidence_ids.extend(fb.evidence_ids)

        payload: dict[str, Any] = {
            "facility": {
                "id": facility.id,
                "name": facility.name,
                "ward": facility.ward,
                "address": facility.address,
                "lat": facility.lat,
                "lng": facility.lng,
            },
            "issue": {
                "id": issue.id,
                "type": issue.type.value,
                "status": issue.status.value,
                "category": issue.category.value,
                "summary": issue.summary,
            },
            "latest_cleanliness_window": (
                {
                    "window_start": latest_window.window_start.isoformat(),
                    "window_end": latest_window.window_end.isoformat(),
                    "yes_count": latest_window.yes_count,
                    "no_count": latest_window.no_count,
                    "total": latest_window.total,
                    "negative_ratio": latest_window.negative_ratio,
                    "verdict": latest_window.verdict.value,
                }
                if latest_window
                else None
            ),
            "official_score": (
                {
                    "value": official_score.value,
                    "computed_at": official_score.computed_at.isoformat(),
                    "source": official_score.source,
                }
                if official_score
                else "score unavailable"
            ),
            "triage": {
                "level": issue.triage_level.value,
                "classification_note": CLASSIFICATION_NOTE,
            },
            "verification_status": facility.verification_status.value,
            "evidence_reference_ids": evidence_ids,
            "generated_at": now.isoformat(),
        }

        subject = (
            f"[Namma Suvidha] {issue.type.value.upper()} alert for "
            f"{facility.name} ({facility.ward})"
        )
        body = (
            f"Facility: {facility.name} (Ward: {facility.ward})\n"
            f"Issue: {issue.summary}\n"
            f"Triage classification: {issue.triage_level.value} ({CLASSIFICATION_NOTE})\n"
            f"Generated at: {now.isoformat()}"
        )

        notif_id = f"ntf-{uuid.uuid4().hex[:10]}"
        initial_record = NotificationRecord(
            id=notif_id,
            issue_id=issue.id,
            channel=NotificationChannel.email,
            recipient=party.email,
            status=NotificationStatus.created,
            created_at=now,
            payload=payload,
        )

        delivery = self._email.send(
            recipient=party.email,
            subject=subject,
            body=body,
            payload=payload,
        )

        if delivery.ok:
            final_record = initial_record.model_copy(
                update={
                    "status": NotificationStatus.sent,
                    "sent_at": delivery.sent_at or now,
                    "provider_message": delivery.provider_message,
                }
            )
            self._issues.attach_notification(issue.id, final_record)
            if issue.status == IssueStatus.open:
                self._issue_service.transition_issue(
                    issue.id,
                    to_status=IssueStatus.alert_sent,
                    actor_id=actor_id,
                    note=f"Alert email sent to {party.email}",
                    now=now,
                )
            else:
                self._issues.append_transition(
                    issue.id,
                    IssueAuditEntry(
                        from_status=issue.status,
                        to_status=issue.status,
                        actor_id=actor_id,
                        note=f"Alert email re-sent to {party.email}",
                        timestamp=now,
                    ),
                    issue.status,
                )
        else:
            final_record = initial_record.model_copy(
                update={
                    "status": NotificationStatus.failed,
                    "sent_at": None,
                    "provider_message": delivery.provider_message,
                }
            )
            self._issues.attach_notification(issue.id, final_record)
            self._issues.append_transition(
                issue.id,
                IssueAuditEntry(
                    from_status=issue.status,
                    to_status=issue.status,
                    actor_id=actor_id,
                    note=f"Alert email delivery failed: {delivery.provider_message}",
                    timestamp=now,
                ),
                issue.status,
            )

        return final_record

    def acknowledge(
        self, issue_id: str, *, actor_id: str, note: str | None, now: datetime
    ) -> MaintenanceIssue:
        issue = self._issues.get(issue_id)
        if issue is None:
            raise ResourceNotFoundError(f"Issue '{issue_id}' not found")

        if issue.notifications:
            latest_notif = issue.notifications[-1]
            self._issues.update_notification_status(
                issue_id,
                latest_notif.id,
                NotificationStatus.acknowledged,
                acknowledged_at=now,
            )

        return self._issue_service.transition_issue(
            issue_id,
            to_status=IssueStatus.acknowledged,
            actor_id=actor_id,
            note=note or "Issue acknowledged by operator/authority",
            now=now,
        )
