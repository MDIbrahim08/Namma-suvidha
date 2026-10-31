"""Platform Audit Event Repository.

OWNER: Internal Admin Audit & Analytics Module

Append-only, immutable event log for platform-wide governance.
Logs cannot be edited or deleted through any client endpoint.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.admin.domain import PlatformAuditEvent


class PlatformAuditRepository:
    def __init__(self) -> None:
        self._events: list[PlatformAuditEvent] = []
        self._seed_initial_events()

    def _seed_initial_events(self) -> None:
        """Seed initial real-world events from Bangalore municipal facilities."""
        now = datetime.now(UTC)

        initial = [
            PlatformAuditEvent(
                event_id="EVT-2026-1001",
                event_type="facility.status_changed",
                description="BBMP Public Restroom Majestic Subway flagged for urgent sanitation review.",
                related_toilet_id="fac-majestic-01",
                toilet_name="Majestic Bus Stand Subway Complex",
                timestamp=now - timedelta(hours=5, minutes=12),
                severity="high",
                actor="system:cleanliness-engine",
                status="pending",
                metadata={"condition": "needs_attention", "ward": "Gandhinagar"},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1002",
                event_type="feedback.submitted",
                description="Citizen submitted complaint: 'Severe ammonia odour, unflushed pans, wet soiled floor.'",
                related_toilet_id="fac-majestic-01",
                toilet_name="Majestic Bus Stand Subway Complex",
                timestamp=now - timedelta(hours=4, minutes=45),
                severity="high",
                actor="citizen:app-user-4821",
                status="success",
                metadata={"category": "cleanliness_hygiene", "severity_score": 5},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1003",
                event_type="ai.classification",
                description="Gemini Intelligence model classified complaint into 'cleanliness_hygiene' with 94% confidence.",
                related_toilet_id="fac-majestic-01",
                toilet_name="Majestic Bus Stand Subway Complex",
                timestamp=now - timedelta(hours=4, minutes=44),
                severity="info",
                actor="system:ai-classifier",
                status="success",
                metadata={"model": "gemini-2.0-flash", "urgency": "urgent"},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1004",
                event_type="inspector.verification_approved",
                description="Infosys CSR Volunteer Ananya Sharma (INF-CSR-2026-101) verified against authorised roster.",
                related_toilet_id=None,
                toilet_name=None,
                timestamp=now - timedelta(hours=4, minutes=10),
                severity="info",
                actor="admin:system-roster",
                status="success",
                metadata={"volunteer_id": "INF-CSR-2026-101", "role": "infosys_csr"},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1005",
                event_type="inspection.completed",
                description="Volunteer Ananya Sharma completed physical invigilation audit. Missing handwash dispenser flagged.",
                related_toilet_id="fac-majestic-01",
                toilet_name="Majestic Bus Stand Subway Complex",
                timestamp=now - timedelta(hours=3, minutes=30),
                severity="medium",
                actor="volunteer:INF-CSR-2026-101",
                status="success",
                metadata={"checklist_score": 60, "honorarium_earned": 250},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1006",
                event_type="facility.score_updated",
                description="Facility hygiene score recalculated to 38.5/100 (Attention Required).",
                related_toilet_id="fac-majestic-01",
                toilet_name="Majestic Bus Stand Subway Complex",
                timestamp=now - timedelta(hours=3, minutes=28),
                severity="high",
                actor="system:intelligence-scorer",
                status="success",
                metadata={"previous_score": 55.0, "new_score": 38.5},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1007",
                event_type="issue.created",
                description="Maintenance ticket created: 'Immediate janitorial deep-clean and water pump restore required.'",
                related_toilet_id="fac-majestic-01",
                toilet_name="Majestic Bus Stand Subway Complex",
                timestamp=now - timedelta(hours=3, minutes=25),
                severity="critical",
                actor="system:cleanliness-service",
                status="pending",
                metadata={"ticket_id": "TKT-BBMP-94-101", "priority": "urgent"},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1008",
                event_type="notification.generated",
                description="Government alert email generated for BBMP West Zone Ward Supervisor Ramesh Kumar.",
                related_toilet_id="fac-majestic-01",
                toilet_name="Majestic Bus Stand Subway Complex",
                timestamp=now - timedelta(hours=3, minutes=24),
                severity="medium",
                actor="system:notification-engine",
                status="success",
                metadata={"recipient": "bbmp.west.sanitation.test@example.org"},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1009",
                event_type="notification.delivery_success",
                description="Official sanitation incident report delivered to BBMP West Zone Supervisor.",
                related_toilet_id="fac-majestic-01",
                toilet_name="Majestic Bus Stand Subway Complex",
                timestamp=now - timedelta(hours=3, minutes=23),
                severity="info",
                actor="provider:smtp-relay",
                status="success",
                metadata={"message_id": "msg-bbmp-94-01"},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1010",
                event_type="issue.escalated",
                description="Automated escalation triggered: Response deadline (2 hours) exceeded without contractor acknowledgement.",
                related_toilet_id="fac-majestic-01",
                toilet_name="Majestic Bus Stand Subway Complex",
                timestamp=now - timedelta(hours=1, minutes=15),
                severity="critical",
                actor="system:escalation-monitor",
                status="escalated",
                metadata={"escalation_level": 1, "target": "Chief Engineer (SWM)"},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1011",
                event_type="issue.resolved",
                description="K.R. Market Eastern Block maintenance ticket resolved: Flush valve replaced and floor sanitized.",
                related_toilet_id="fac-krmarket-02",
                toilet_name="K.R. Market Eastern Block Facility",
                timestamp=now - timedelta(minutes=45),
                severity="low",
                actor="admin:supervisor-kiran",
                status="resolved",
                metadata={"ticket_id": "TKT-BBMP-109-02", "resolution_notes": "Plumbing contractor verified on-site."},
            ),
            PlatformAuditEvent(
                event_id="EVT-2026-1012",
                event_type="feedback.submitted",
                description="Citizen submitted rating: 5/5 Stars. Clean, wheelchair accessible with running tap water.",
                related_toilet_id="fac-indiranagar-03",
                toilet_name="Indiranagar 100ft Road Namma Toilet",
                timestamp=now - timedelta(minutes=20),
                severity="info",
                actor="citizen:app-user-9182",
                status="success",
                metadata={"category": "cleanliness_hygiene", "sentiment": "positive"},
            ),
        ]
        self._events.extend(initial)

    def append(self, event: PlatformAuditEvent) -> PlatformAuditEvent:
        """Append a new immutable audit record to the store."""
        self._events.append(event)
        return event

    def list_events(
        self,
        *,
        event_type: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        search_query: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PlatformAuditEvent], int]:
        filtered = self._events

        if event_type:
            clean_type = event_type.strip().lower()
            filtered = [e for e in filtered if clean_type in e.event_type.lower()]

        if severity:
            clean_sev = severity.strip().lower()
            filtered = [e for e in filtered if e.severity.lower() == clean_sev]

        if status:
            clean_st = status.strip().lower()
            filtered = [e for e in filtered if e.status.lower() == clean_st]

        if start_date:
            filtered = [e for e in filtered if e.timestamp >= start_date]

        if end_date:
            filtered = [e for e in filtered if e.timestamp <= end_date]

        if search_query:
            q = search_query.strip().lower()
            filtered = [
                e
                for e in filtered
                if q in e.description.lower()
                or q in e.event_id.lower()
                or (e.toilet_name and q in e.toilet_name.lower())
                or (e.related_toilet_id and q in e.related_toilet_id.lower())
                or q in e.actor.lower()
            ]

        # Reverse chronological order (newest first)
        sorted_events = sorted(filtered, key=lambda e: e.timestamp, reverse=True)
        total = len(sorted_events)
        paginated = sorted_events[offset : offset + limit]
        return paginated, total


_AUDIT_REPO_INSTANCE: PlatformAuditRepository | None = None


def get_platform_audit_repository() -> PlatformAuditRepository:
    global _AUDIT_REPO_INSTANCE
    if _AUDIT_REPO_INSTANCE is None:
        _AUDIT_REPO_INSTANCE = PlatformAuditRepository()
    return _AUDIT_REPO_INSTANCE

