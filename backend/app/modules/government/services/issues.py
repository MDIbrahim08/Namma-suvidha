"""Maintenance and cleaning issue lifecycle, transitions, and audit history.

OWNER: Ibrahim

Single source of truth for allowed status transitions: `ALLOWED_ISSUE_TRANSITIONS`.
"""

import uuid
from datetime import datetime

from app.modules.government.config import GovernmentSettings
from app.modules.government.domain import (
    IssueAuditEntry,
    MaintenanceDetectionSummary,
    MaintenanceIssue,
)
from app.modules.government.enums import (
    FeedbackCategory,
    IssueStatus,
    IssueType,
    TriageLevel,
    VerificationStatus,
)
from app.modules.government.exceptions import (
    IllegalIssueTransitionError,
    InvalidTransitionNoteError,
    ResourceNotFoundError,
)
from app.modules.government.interfaces import (
    CleanlinessRepository,
    FacilityRepository,
    FacilityScoreProvider,
    FeedbackRepository,
    IssueFilterParams,
    IssueRepository,
)
from app.modules.government.services.cleanliness import check_facility_low_usage
from app.modules.government.services.priority import classify_facility_triage

# Single dictionary — the ONLY source of truth for issue status transitions.
ALLOWED_ISSUE_TRANSITIONS: dict[IssueStatus, set[IssueStatus]] = {
    IssueStatus.open: {IssueStatus.alert_sent, IssueStatus.dismissed},
    IssueStatus.alert_sent: {
        IssueStatus.acknowledged,
        IssueStatus.escalated,
        IssueStatus.dismissed,
    },
    IssueStatus.acknowledged: {IssueStatus.resolved, IssueStatus.escalated},
    IssueStatus.escalated: {IssueStatus.acknowledged, IssueStatus.resolved},
    IssueStatus.resolved: set(),
    IssueStatus.dismissed: set(),
}

NOTE_REQUIRED_STATUSES = {IssueStatus.resolved, IssueStatus.dismissed}


class IssueService:
    def __init__(
        self,
        issue_repo: IssueRepository,
        facility_repo: FacilityRepository,
        feedback_repo: FeedbackRepository,
        cleanliness_repo: CleanlinessRepository,
        score_provider: FacilityScoreProvider,
        settings: GovernmentSettings,
    ) -> None:
        self._issues = issue_repo
        self._facilities = facility_repo
        self._feedback = feedback_repo
        self._cleanliness = cleanliness_repo
        self._scores = score_provider
        self._settings = settings

    def create_issue(
        self,
        *,
        issue_type: IssueType,
        facility_id: str,
        ward: str | None,
        category: FeedbackCategory,
        triage_level: TriageLevel,
        summary: str,
        responsibility_unverified: bool,
        consecutive_negative_windows: int,
        actor_id: str,
        initial_note: str,
        now: datetime,
    ) -> MaintenanceIssue:
        issue_id = f"iss-{uuid.uuid4().hex[:10]}"
        initial_entry = IssueAuditEntry(
            from_status=None,
            to_status=IssueStatus.open,
            actor_id=actor_id,
            note=initial_note,
            timestamp=now,
        )
        issue = MaintenanceIssue(
            id=issue_id,
            type=issue_type,
            status=IssueStatus.open,
            facility_id=facility_id,
            ward=ward,
            category=category,
            triage_level=triage_level,
            summary=summary,
            responsibility_unverified=responsibility_unverified,
            consecutive_negative_windows=consecutive_negative_windows,
            verification_requested_at=None,
            created_at=now,
            updated_at=now,
            history=[initial_entry],
            notifications=[],
        )
        return self._issues.create(issue)

    def get_issue(self, issue_id: str) -> MaintenanceIssue:
        issue = self._issues.get(issue_id)
        if issue is None:
            raise ResourceNotFoundError(f"Issue '{issue_id}' not found")
        return issue

    def list_issues(self, filters: IssueFilterParams) -> list[MaintenanceIssue]:
        return self._issues.list(filters)

    def transition_issue(
        self,
        issue_id: str,
        *,
        to_status: IssueStatus,
        actor_id: str,
        note: str | None,
        now: datetime,
    ) -> MaintenanceIssue:
        issue = self.get_issue(issue_id)
        from_status = issue.status

        cleaned_note = (note or "").strip()
        if to_status in NOTE_REQUIRED_STATUSES and not cleaned_note:
            raise InvalidTransitionNoteError(
                f"Transitioning to '{to_status.value}' requires a non-empty note."
            )

        allowed = ALLOWED_ISSUE_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise IllegalIssueTransitionError(
                f"Illegal transition '{from_status.value} -> {to_status.value}' "
                f"for issue '{issue_id}'."
            )

        if to_status == IssueStatus.escalated and issue.verification_requested_at is None:
            self._issues.update_counters(
                issue_id,
                consecutive_negative_windows=issue.consecutive_negative_windows,
                verification_requested_at=now,
                updated_at=now,
            )

        entry = IssueAuditEntry(
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            note=cleaned_note or f"Transitioned {from_status.value} -> {to_status.value}",
            timestamp=now,
        )
        return self._issues.append_transition(issue_id, entry, to_status)

    def detect_maintenance(
        self, now: datetime, actor_id: str = "system-evaluate"
    ) -> MaintenanceDetectionSummary:
        """Create `type=maintenance` issues for urgent/high non-cleaning triage."""
        facilities = self._facilities.list()
        summary = MaintenanceDetectionSummary(
            evaluated_at=now,
            facilities_considered=len(facilities),
        )

        for fac in facilities:
            score = self._scores.get_score(fac.id)
            clusters = self._feedback.repeated_clusters(
                now=now,
                window_days=self._settings.REPEAT_WINDOW_DAYS,
                min_count=self._settings.REPEAT_MIN_COUNT,
                min_reporters=self._settings.REPEAT_MIN_REPORTERS,
                facility_id=fac.id,
            )
            non_cleaning_clusters = [
                c
                for c in clusters
                if c.category != FeedbackCategory.cleanliness_hygiene
            ]
            low_usage, _ = check_facility_low_usage(
                self._cleanliness, fac.id, now, self._settings
            )

            # Evaluate triage without active cleaning issue so only non-cleaning
            # signals trigger maintenance
            triage = classify_facility_triage(
                official_score=score,
                repeated_clusters=non_cleaning_clusters,
                active_cleaning_issue_status=None,
                has_any_feedback=bool(non_cleaning_clusters),
                inspection_stale=False,
                low_usage=low_usage,
                verification_status=fac.verification_status,
                settings=self._settings,
            )

            if triage.level not in {TriageLevel.urgent, TriageLevel.high}:
                continue

            category = (
                non_cleaning_clusters[0].category
                if non_cleaning_clusters
                else FeedbackCategory.broken_equipment
            )
            existing = self._issues.find_open(
                fac.id, IssueType.maintenance, category
            )
            if existing is not None:
                self._issues.append_transition(
                    existing.id,
                    IssueAuditEntry(
                        from_status=existing.status,
                        to_status=existing.status,
                        actor_id=actor_id,
                        note=f"Maintenance detection re-confirmed ({'; '.join(triage.reasons)})",
                        timestamp=now,
                    ),
                    existing.status,
                )
                summary.existing_issues_noted += 1
                continue

            verified_party = (
                fac.verification_status == VerificationStatus.verified
                and fac.responsible_party is not None
                and fac.responsible_party.verified
                and bool(fac.responsible_party.email)
            )
            created = self.create_issue(
                issue_type=IssueType.maintenance,
                facility_id=fac.id,
                ward=fac.ward,
                category=category,
                triage_level=triage.level,
                summary=f"Maintenance required ({category.value}): {'; '.join(triage.reasons)}",
                responsibility_unverified=not verified_party,
                consecutive_negative_windows=0,
                actor_id=actor_id,
                initial_note="Created by maintenance detection",
                now=now,
            )
            summary.issues_created += 1
            summary.created_issue_ids.append(created.id)

        return summary
