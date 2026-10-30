"""Feedback-driven cleaning aggregation and low-usage guard.

OWNER: Ibrahim

Execution model:
`evaluate(now)` is called synchronously by `POST /api/v1/government/evaluate`.
It processes the single most recent COMPLETE window aligned to
`GOV_CLEAN_WINDOW_MINUTES` ending at or before `now`. If `/evaluate` was not
called for earlier windows, those windows are NOT backfilled in this MVP —
the raw cleanliness responses remain stored, but no historical window verdict
is retroactively generated. No scheduler, timer, or background worker exists
in Phase 2.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.modules.government.config import GovernmentSettings
from app.modules.government.domain import (
    EVALUATION_NO_BACKFILL_NOTE,
    CleanlinessWindow,
    EvaluationSummary,
    IssueAuditEntry,
)
from app.modules.government.enums import (
    CleanlinessVerdict,
    FeedbackCategory,
    IssueStatus,
    IssueType,
    TriageLevel,
    VerificationStatus,
)
from app.modules.government.interfaces import (
    CleanlinessRepository,
    FacilityRepository,
    IssueRepository,
)

if TYPE_CHECKING:
    from app.modules.government.services.issues import IssueService
    from app.modules.government.services.notifications import NotificationService


def compute_latest_complete_window(
    now: datetime, window_minutes: int
) -> tuple[datetime, datetime]:
    """Return `(window_start, window_end)` for the latest complete window ending <= `now`."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    else:
        now = now.astimezone(UTC)

    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    window_seconds = window_minutes * 60
    elapsed_seconds = int((now - epoch).total_seconds())
    aligned_end_seconds = (elapsed_seconds // window_seconds) * window_seconds
    window_end = epoch + timedelta(seconds=aligned_end_seconds)
    window_start = window_end - timedelta(seconds=window_seconds)
    return window_start, window_end


def check_facility_low_usage(
    cleanliness_repo: CleanlinessRepository,
    facility_id: str,
    now: datetime,
    settings: GovernmentSettings,
) -> tuple[bool, bool]:
    """Return `(low_usage, cleanliness_unknown)` for a single facility over the 24h window.

    Absence of negative feedback is NEVER treated as cleanliness: if a facility
    received fewer than `CLEAN_MIN_RESPONSES` (including zero) in the last
    `CLEAN_LOW_USAGE_HOURS`, both flags are `True`.
    """
    start = now - timedelta(hours=settings.CLEAN_LOW_USAGE_HOURS)
    count = cleanliness_repo.count_responses(facility_id, start, now)
    if count < settings.CLEAN_MIN_RESPONSES:
        return True, True
    return False, False


class CleanlinessService:
    def __init__(
        self,
        facility_repo: FacilityRepository,
        cleanliness_repo: CleanlinessRepository,
        issue_repo: IssueRepository,
        settings: GovernmentSettings,
        issue_service: "IssueService | None" = None,
        notification_service: "NotificationService | None" = None,
    ) -> None:
        self._facilities = facility_repo
        self._cleanliness = cleanliness_repo
        self._issues = issue_repo
        self._settings = settings
        self._issue_service = issue_service
        self._notification_service = notification_service

    def evaluate(self, now: datetime, actor_id: str = "system-evaluate") -> EvaluationSummary:
        window_start, window_end = compute_latest_complete_window(
            now, self._settings.CLEAN_WINDOW_MINUTES
        )
        all_ids = self._facilities.list_all_ids()

        summary = EvaluationSummary(
            window_start=window_start,
            window_end=window_end,
            facilities_considered=len(all_ids),
            note=EVALUATION_NO_BACKFILL_NOTE,
        )

        for facility_id in all_ids:
            low_usage, _ = check_facility_low_usage(
                self._cleanliness, facility_id, now, self._settings
            )
            if low_usage:
                summary.low_usage_flagged += 1

            if self._cleanliness.window_exists(facility_id, window_start):
                summary.skipped_existing += 1
                continue

            responses = self._cleanliness.responses_for_facility(
                facility_id, window_start, window_end
            )
            yes_count = sum(1 for r in responses if r.is_clean)
            no_count = sum(1 for r in responses if not r.is_clean)
            total = len(responses)
            negative_ratio = round(no_count / total, 4) if total > 0 else 0.0

            if total < self._settings.CLEAN_MIN_RESPONSES:
                verdict = CleanlinessVerdict.insufficient_data
                action = "insufficient_data"
                reasons = ["Below minimum responses; cleanliness unknown"]
                summary.insufficient_data += 1
            elif (no_count / total) >= self._settings.CLEAN_NEGATIVE_RATIO:
                verdict = CleanlinessVerdict.needs_cleaning
                action = "alert"
                reasons = [
                    f"Negative ratio {no_count}/{total} ({negative_ratio:.2f}) "
                    f">= threshold {self._settings.CLEAN_NEGATIVE_RATIO:.2f}"
                ]
                summary.needs_cleaning += 1
            else:
                verdict = CleanlinessVerdict.clean
                action = "none"
                reasons = ["Predominantly positive; no dispatch recommended"]
                summary.clean += 1

            # Save the window first so any alert email triggered below includes
            # `latest_cleanliness_window` in its structured payload.
            active_issue = self._issues.find_open(
                facility_id, IssueType.cleaning, FeedbackCategory.cleanliness_hygiene
            )
            if (
                verdict == CleanlinessVerdict.needs_cleaning
                and active_issue is not None
                and (active_issue.consecutive_negative_windows + 1)
                >= self._settings.CLEAN_ESCALATE_AFTER_WINDOWS
                and active_issue.status != IssueStatus.escalated
            ):
                action = "escalate"

            window = CleanlinessWindow(
                facility_id=facility_id,
                window_start=window_start,
                window_end=window_end,
                yes_count=yes_count,
                no_count=no_count,
                total=total,
                negative_ratio=negative_ratio,
                verdict=verdict,
                action=action,  # type: ignore[arg-type]
                reasons=reasons,
            )
            self._cleanliness.save_window(window)
            summary.windows_saved += 1

            # Handle active issue / alert / escalation when issue_service is wired
            if verdict == CleanlinessVerdict.needs_cleaning and self._issue_service is not None:
                facility = self._facilities.get(facility_id)
                if active_issue is None:
                    action = "alert"
                    verified_party = (
                        facility is not None
                        and facility.verification_status == VerificationStatus.verified
                        and facility.responsible_party is not None
                        and facility.responsible_party.verified
                        and bool(facility.responsible_party.email)
                    )
                    initial_note = (
                        "Cleaning alert created from negative cleanliness window"
                        if verified_party
                        else "No verified operator contact — manual follow-up required"
                    )
                    issue = self._issue_service.create_issue(
                        issue_type=IssueType.cleaning,
                        facility_id=facility_id,
                        ward=facility.ward if facility else None,
                        category=FeedbackCategory.cleanliness_hygiene,
                        triage_level=TriageLevel.high,
                        summary=(
                            f"Feedback-driven cleaning alert: {no_count}/{total} NO responses "
                            f"in window {window_start.isoformat()}"
                        ),
                        responsibility_unverified=not verified_party,
                        consecutive_negative_windows=0,
                        actor_id=actor_id,
                        initial_note=initial_note,
                        now=now,
                    )
                    summary.alerts_created += 1
                    summary.affected_facility_ids.append(facility_id)
                    summary.affected_issue_ids.append(issue.id)

                    if (
                        verified_party
                        and self._settings.CLEAN_AUTO_NOTIFY
                        and self._notification_service
                    ):
                        notif = self._notification_service.send_alert(
                            issue.id, actor_id=actor_id, now=now
                        )
                        if notif.status.value == "sent":
                            summary.alerts_emailed += 1
                    elif not verified_party:
                        summary.alerts_without_recipient += 1
                else:
                    new_count = active_issue.consecutive_negative_windows + 1
                    verification_at = active_issue.verification_requested_at
                    if (
                        new_count >= self._settings.CLEAN_ESCALATE_AFTER_WINDOWS
                        and active_issue.status != IssueStatus.escalated
                    ):
                        action = "escalate"
                        verification_at = now
                        self._issues.update_counters(
                            active_issue.id,
                            consecutive_negative_windows=new_count,
                            verification_requested_at=verification_at,
                            updated_at=now,
                        )
                        escalation_note = (
                            "Negative feedback persisted after alert — "
                            "physical verification required"
                        )
                        if active_issue.status == IssueStatus.open:
                            # Record escalation when no verified recipient existed
                            self._issues.append_transition(
                                active_issue.id,
                                IssueAuditEntry(
                                    from_status=active_issue.status,
                                    to_status=IssueStatus.escalated,
                                    actor_id=actor_id,
                                    note=escalation_note,
                                    timestamp=now,
                                ),
                                IssueStatus.escalated,
                            )
                        else:
                            self._issue_service.transition_issue(
                                active_issue.id,
                                to_status=IssueStatus.escalated,
                                actor_id=actor_id,
                                note=escalation_note,
                                now=now,
                            )
                        summary.escalations += 1
                        summary.affected_facility_ids.append(facility_id)
                        summary.affected_issue_ids.append(active_issue.id)
                    else:
                        action = "alert"
                        self._issues.update_counters(
                            active_issue.id,
                            consecutive_negative_windows=new_count,
                            verification_requested_at=verification_at,
                            updated_at=now,
                        )
            elif verdict == CleanlinessVerdict.clean and active_issue is not None:
                self._issues.update_counters(
                    active_issue.id,
                    consecutive_negative_windows=0,
                    verification_requested_at=active_issue.verification_requested_at,
                    updated_at=now,
                )
                self._issues.append_transition(
                    active_issue.id,
                    IssueAuditEntry(
                        from_status=active_issue.status,
                        to_status=active_issue.status,
                        actor_id=actor_id,
                        note="Positive window observed",
                        timestamp=now,
                    ),
                    active_issue.status,
                )

        return summary
