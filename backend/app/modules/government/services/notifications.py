"""Automated Government Notification & Incident Management Service.

OWNER: Ibrahim / Government Automated Notification System

Backend-driven notification pipeline:
1. Generates structured 11-point incident reports.
2. Identifies responsible city corporation/ward department from configured contacts.
3. Sends email/SMS to verified official contacts.
4. Stores notification records and tracks delivery status.
5. Prevents duplicate alerts for the same unresolved incident.
6. Triggers automated escalation notifications when response deadlines are missed.
7. Maintains comprehensive audit logs accessible internally.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.government.config import GovernmentSettings
from app.modules.government.contacts import (
    OfficialContact,
    OfficialContactDirectory,
    get_official_contact_directory,
)
from app.modules.government.domain import (
    CLASSIFICATION_NOTE,
    GovernmentAuditRecord,
    IssueAuditEntry,
    MaintenanceIssue,
    NotificationRecord,
    StructuredIncidentReport,
)
from app.modules.government.enums import (
    IssueStatus,
    NotificationChannel,
    NotificationStatus,
    TriageLevel,
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
from app.modules.government.providers.sms import SMSProvider, TestSMSProvider
from app.modules.government.services.issues import IssueService

logger = logging.getLogger("namma_suvidha.government.notifications")


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
        contacts_directory: OfficialContactDirectory | None = None,
        sms_provider: SMSProvider | None = None,
    ) -> None:
        self._issues = issue_repo
        self._facilities = facility_repo
        self._feedback = feedback_repo
        self._cleanliness = cleanliness_repo
        self._scores = score_provider
        self._email = email_provider
        self._issue_service = issue_service
        self._settings = settings
        self._contacts = contacts_directory or get_official_contact_directory()
        self._sms = sms_provider or TestSMSProvider()
        self._audit_logs: list[GovernmentAuditRecord] = []

    def log_audit_event(
        self,
        event_type: Any,
        incident_id: str,
        facility_id: str,
        now: datetime,
        recipient: str | None = None,
        delivery_status: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> GovernmentAuditRecord:
        record = GovernmentAuditRecord(
            id=f"audit-{uuid.uuid4().hex[:10]}",
            event_type=event_type,
            incident_id=incident_id,
            facility_id=facility_id,
            recipient=recipient,
            delivery_status=delivery_status,
            timestamp=now,
            details=details or {},
        )
        self._audit_logs.append(record)
        return record

    def list_audit_records(
        self,
        incident_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[GovernmentAuditRecord]:
        records = self._audit_logs
        if incident_id:
            records = [r for r in records if r.incident_id == incident_id]
        if event_type:
            records = [r for r in records if r.event_type == event_type]
        return records[-limit:]

    def generate_incident_report(
        self,
        issue: MaintenanceIssue,
        now: datetime,
        escalation_level: int = 0,
    ) -> StructuredIncidentReport:
        facility = self._facilities.get(issue.facility_id)
        toilet_name = facility.name if facility else "Bengaluru Public Washroom"
        address = facility.address if facility else None
        location = {
            "latitude": facility.lat if facility else None,
            "longitude": facility.lng if facility else None,
        }

        # Related citizen feedback items
        feedback_items = self._feedback.list_for_facility(issue.facility_id)
        complaints_count = len(feedback_items)

        # Citizen feedback summary
        if feedback_items:
            comments = [fb.comment for fb in feedback_items if fb.comment]
            feedback_summary = (
                "; ".join(comments[:3])
                if comments
                else f"{complaints_count} citizen complaints logged for {issue.category.value}."
            )
        else:
            feedback_summary = issue.summary

        # Volunteer inspection findings
        latest_insp = self._facilities.latest_inspection(issue.facility_id) if facility else None
        volunteer_findings = None
        if latest_insp:
            volunteer_findings = {
                "inspection_id": latest_insp.inspection_id,
                "evaluator_id": latest_insp.evaluator_id,
                "inspected_at": latest_insp.inspected_at.isoformat(),
                "checklist_passed": latest_insp.checklist_passed,
                "summary_note": latest_insp.summary_note,
                "evidence_ids": latest_insp.evidence_ids,
            }

        # Determine severity and response deadline based on triage level
        if issue.triage_level == TriageLevel.urgent:
            severity = 5
            priority = "urgent"
            deadline = issue.created_at + timedelta(hours=2)
            recommended_action = (
                "IMMEDIATE ACTION (within 2h): Dispatch emergency BBMP sanitation crew for "
                "ammonia neutralisation, deep pressure wash, pan unclogging, and chemical disinfection."
            )
        elif issue.triage_level == TriageLevel.high:
            severity = 4
            priority = "high"
            deadline = issue.created_at + timedelta(hours=8)
            recommended_action = (
                "PRIORITY ACTION (within 8h): Deploy ward maintenance team to inspect water supply, "
                "refill soap/sanitiser dispensers, and repair defective fixtures."
            )
        else:
            severity = 3
            priority = "normal"
            deadline = issue.created_at + timedelta(hours=24)
            recommended_action = (
                "ROUTINE ACTION (within 24h): Carry out routine cleaning cycle and preventive maintenance audit."
            )

        incident_id = f"INC-{issue.facility_id[-8:].upper()}-{issue.id[-6:].upper()}"
        is_overdue = now > deadline

        return StructuredIncidentReport(
            incident_id=incident_id,
            toilet_name=toilet_name,
            toilet_id=issue.facility_id,
            facility_address=address,
            facility_location=location,
            issue_category=issue.category.value,
            related_complaints_count=complaints_count,
            severity=severity,
            priority=priority,
            citizen_feedback_summary=feedback_summary,
            volunteer_inspection_findings=volunteer_findings,
            recommended_maintenance_action=recommended_action,
            detected_at=issue.created_at,
            response_deadline=deadline,
            escalation_level=escalation_level,
            is_overdue=is_overdue,
        )

    def _resolve_recipient(
        self,
        facility: Any,
        for_escalation: bool = False,
    ) -> tuple[str, str | None, str]:
        """Resolve recipient email, phone, and name using facility or configured contact directory."""
        # 1. Check facility responsible party if verified
        party = facility.responsible_party if facility else None
        if (
            not for_escalation
            and facility
            and facility.verification_status == VerificationStatus.verified
            and party
            and party.verified
            and party.email
        ):
            return party.email, party.phone, party.name

        # 2. Query configured Official Contact Directory using ward / corporation mapping
        ward = facility.ward if facility else None
        contact = self._contacts.resolve_contact(ward=ward, for_escalation=for_escalation)
        if contact and contact.active:
            return contact.official_email, contact.office_phone, contact.recipient_name

        # 3. Fallback to supervisor or raise if absolutely none
        if party and party.email:
            return party.email, party.phone, party.name

        raise MissingVerifiedRecipientError(
            f"No verified official recipient configured for facility '{facility.id if facility else 'unknown'}' (Ward: {ward})."
        )

    def send_alert(
        self,
        issue_id: str,
        *,
        actor_id: str,
        now: datetime,
        channel: NotificationChannel = NotificationChannel.email,
        force_resend: bool = False,
    ) -> NotificationRecord:
        issue = self._issues.get(issue_id)
        if issue is None:
            raise ResourceNotFoundError(f"Issue '{issue_id}' not found")

        facility = self._facilities.get(issue.facility_id)
        if facility is None:
            raise ResourceNotFoundError(f"Facility '{issue.facility_id}' not found")

        # 1. Avoid duplicate alerts for the same unresolved incident unless forced
        if not force_resend and issue.notifications:
            for existing in reversed(issue.notifications):
                if (
                    existing.status == NotificationStatus.sent
                    and issue.status in {IssueStatus.alert_sent, IssueStatus.open}
                ):
                    logger.info(
                        "Suppressed duplicate alert for unresolved issue %s (previous sent at %s)",
                        issue_id,
                        existing.sent_at,
                    )
                    return existing

        # 2. Identify the responsible city corporation, ward or relevant department
        recipient_email, recipient_phone, recipient_name = self._resolve_recipient(
            facility, for_escalation=False
        )

        # 3. Generate structured 11-point incident report
        report = self.generate_incident_report(issue, now, escalation_level=0)

        # 4. Construct payload and message body
        payload: dict[str, Any] = {
            "incident_report": report.model_dump(mode="json"),
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
            "triage": {
                "level": issue.triage_level.value,
                "classification_note": CLASSIFICATION_NOTE,
            },
            "generated_at": now.isoformat(),
        }

        subject = (
            f"[BBMP Sanitation Alert] {report.incident_id} - {issue.type.value.upper()} "
            f"({report.priority.upper()}) at {facility.name} ({facility.ward or 'Central'})"
        )
        body = (
            f"GOVERNMENT SANITATION INCIDENT REPORT\n"
            f"----------------------------------------\n"
            f"Incident ID        : {report.incident_id}\n"
            f"Facility           : {report.toilet_name} (ID: {report.toilet_id})\n"
            f"Address            : {report.facility_address or 'Bengaluru Public Location'}\n"
            f"Coordinates        : {report.facility_location.get('latitude')}, {report.facility_location.get('longitude')}\n"
            f"Ward / Division    : {facility.ward or 'Central'}\n"
            f"Issue Category     : {report.issue_category}\n"
            f"Severity / Priority: {report.severity}/5 ({report.priority.upper()})\n"
            f"Complaints Count   : {report.related_complaints_count}\n"
            f"Citizen Feedback   : {report.citizen_feedback_summary}\n"
            f"Inspection Note    : {report.volunteer_inspection_findings.get('summary_note') if report.volunteer_inspection_findings else 'Awaiting verified volunteer inspection.'}\n"
            f"Action Required    : {report.recommended_maintenance_action}\n"
            f"Detected At        : {report.detected_at.isoformat()}\n"
            f"Response Deadline  : {report.response_deadline.isoformat()}\n"
            f"Designated Official: {recipient_name} <{recipient_email}>\n"
            f"----------------------------------------\n"
            f"Please acknowledge and dispatch corrective maintenance before the deadline.\n"
        )

        notif_id = f"ntf-{uuid.uuid4().hex[:10]}"
        initial_record = NotificationRecord(
            id=notif_id,
            issue_id=issue.id,
            channel=channel,
            recipient=recipient_email,
            status=NotificationStatus.created,
            created_at=now,
            payload=payload,
        )

        # 5. Send notification via configured channel
        if channel == NotificationChannel.email:
            delivery = self._email.send(
                recipient=recipient_email,
                subject=subject,
                body=body,
                payload=payload,
            )
        elif channel == NotificationChannel.sms:
            if not recipient_phone:
                delivery = self._sms.send(
                    phone="+91-80-22220000",
                    message=f"BBMP Alert {report.incident_id}: {issue.summary}. Deadline: {report.response_deadline.strftime('%H:%M')}",
                )
            else:
                delivery = self._sms.send(
                    phone=recipient_phone,
                    message=f"BBMP Alert {report.incident_id}: {issue.summary}. Deadline: {report.response_deadline.strftime('%H:%M')}",
                )
        else:
            raise UnsupportedNotificationChannelError(
                f"Notification channel '{channel.value}' is not supported."
            )

        # 6. Store notification and delivery status
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
                    note=f"Alert email sent to {recipient_email} ({recipient_name})",
                    now=now,
                )
            else:
                self._issues.append_transition(
                    issue.id,
                    IssueAuditEntry(
                        from_status=issue.status,
                        to_status=issue.status,
                        actor_id=actor_id,
                        note=f"Alert email sent to {recipient_email} ({recipient_name})",
                        timestamp=now,
                    ),
                    issue.status,
                )
            # Log audit record
            self.log_audit_event(
                event_type="notification_generation",
                incident_id=report.incident_id,
                facility_id=facility.id,
                recipient=recipient_email,
                delivery_status="sent",
                now=now,
                details={
                    "notification_id": notif_id,
                    "channel": channel.value,
                    "priority": report.priority,
                    "response_deadline": report.response_deadline.isoformat(),
                },
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
            self.log_audit_event(
                event_type="notification_generation",
                incident_id=report.incident_id,
                facility_id=facility.id,
                recipient=recipient_email,
                delivery_status="failed",
                now=now,
                details={
                    "notification_id": notif_id,
                    "error": delivery.provider_message,
                },
            )

        return final_record

    def check_and_escalate_overdue_issues(
        self,
        now: datetime,
        actor_id: str = "system-escalation",
    ) -> list[NotificationRecord]:
        """Trigger escalation notifications when the configured response deadline is missed."""
        escalated_records: list[NotificationRecord] = []
        all_issues = self._issues.list()

        for issue in all_issues:
            # Check issues that are in open, alert_sent, or acknowledged status
            if issue.status in {IssueStatus.resolved, IssueStatus.dismissed, IssueStatus.escalated}:
                continue

            report = self.generate_incident_report(issue, now, escalation_level=0)
            if now <= report.response_deadline:
                continue

            # Response deadline is missed -> trigger automated escalation
            facility = self._facilities.get(issue.facility_id)
            if not facility:
                continue

            escalation_email, escalation_phone, escalation_name = self._resolve_recipient(
                facility, for_escalation=True
            )

            # Update report for escalation
            escalated_report = self.generate_incident_report(issue, now, escalation_level=1)
            escalated_report.is_overdue = True

            escalation_subject = (
                f"[ESCALATION - OVERDUE] Missed Response Deadline for Incident {escalated_report.incident_id} "
                f"at {facility.name} (Ward: {facility.ward})"
            )
            escalation_body = (
                f"*** URGENT GOVERNMENT SANITATION ESCALATION NOTICE ***\n"
                f"------------------------------------------------------\n"
                f"Incident ID        : {escalated_report.incident_id}\n"
                f"Facility           : {escalated_report.toilet_name} (ID: {escalated_report.toilet_id})\n"
                f"Ward               : {facility.ward}\n"
                f"Detected At        : {escalated_report.detected_at.isoformat()}\n"
                f"Original Deadline  : {escalated_report.response_deadline.isoformat()} (EXPIRED)\n"
                f"Action Required    : {escalated_report.recommended_maintenance_action}\n"
                f"Escalation Level   : 1 (Zonal Head / Chief Engineer SWM)\n"
                f"Designated Official: {escalation_name} <{escalation_email}>\n"
                f"------------------------------------------------------\n"
                f"The scheduled response window for this issue has expired without resolution.\n"
                f"Immediate administrative intervention and contractor inspection is requested.\n"
            )

            payload = {
                "incident_report": escalated_report.model_dump(mode="json"),
                "is_escalation": True,
                "escalated_at": now.isoformat(),
            }

            delivery = self._email.send(
                recipient=escalation_email,
                subject=escalation_subject,
                body=escalation_body,
                payload=payload,
            )

            notif_id = f"ntf-esc-{uuid.uuid4().hex[:8]}"
            notif_record = NotificationRecord(
                id=notif_id,
                issue_id=issue.id,
                channel=NotificationChannel.email,
                recipient=escalation_email,
                status=NotificationStatus.sent if delivery.ok else NotificationStatus.failed,
                created_at=now,
                sent_at=now if delivery.ok else None,
                provider_message=delivery.provider_message,
                payload=payload,
            )
            self._issues.attach_notification(issue.id, notif_record)

            # Transition issue status to escalated
            self._issue_service.transition_issue(
                issue.id,
                to_status=IssueStatus.escalated,
                actor_id=actor_id,
                note=f"Escalation notification dispatched to {escalation_email} due to missed deadline ({report.response_deadline.isoformat()})",
                now=now,
            )

            # Log escalation audit event
            self.log_audit_event(
                event_type="escalation_event",
                incident_id=escalated_report.incident_id,
                facility_id=facility.id,
                recipient=escalation_email,
                delivery_status="sent" if delivery.ok else "failed",
                now=now,
                details={
                    "original_deadline": report.response_deadline.isoformat(),
                    "escalation_level": 1,
                    "notification_id": notif_id,
                },
            )
            escalated_records.append(notif_record)

        return escalated_records

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

        updated_issue = self._issue_service.transition_issue(
            issue_id,
            to_status=IssueStatus.acknowledged,
            actor_id=actor_id,
            note=note or "Issue acknowledged by operator/authority",
            now=now,
        )

        incident_id = f"INC-{issue.facility_id[-8:].upper()}-{issue.id[-6:].upper()}"
        self.log_audit_event(
            event_type="status_transition",
            incident_id=incident_id,
            facility_id=issue.facility_id,
            now=now,
            details={"to_status": IssueStatus.acknowledged.value, "note": note},
        )
        return updated_issue

    def resolve(
        self, issue_id: str, *, actor_id: str, note: str, now: datetime
    ) -> MaintenanceIssue:
        issue = self._issues.get(issue_id)
        if issue is None:
            raise ResourceNotFoundError(f"Issue '{issue_id}' not found")

        updated_issue = self._issue_service.transition_issue(
            issue_id,
            to_status=IssueStatus.resolved,
            actor_id=actor_id,
            note=note,
            now=now,
        )

        incident_id = f"INC-{issue.facility_id[-8:].upper()}-{issue.id[-6:].upper()}"
        self.log_audit_event(
            event_type="maintenance_resolution",
            incident_id=incident_id,
            facility_id=issue.facility_id,
            now=now,
            details={"to_status": IssueStatus.resolved.value, "resolution_note": note},
        )
        return updated_issue
