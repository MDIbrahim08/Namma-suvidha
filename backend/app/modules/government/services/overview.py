"""Government overview statistics service.

OWNER: Ibrahim

Computes all statistics directly from repositories. An empty repository source
returns zeros for every counter. Citizen feedback and evaluator inspections are
kept strictly separate.
"""

from datetime import datetime, timedelta
from typing import Literal

from app.modules.government.config import GovernmentSettings
from app.modules.government.domain import OverviewStatistics
from app.modules.government.enums import (
    ConditionBand,
    FeedbackSentiment,
    FeedbackSource,
    IssueStatus,
    IssueType,
    VerificationStatus,
)
from app.modules.government.interfaces import (
    CleanlinessRepository,
    FacilityRepository,
    FacilityScoreProvider,
    FeedbackFilterParams,
    FeedbackRepository,
    IssueFilterParams,
    IssueRepository,
)
from app.modules.government.repositories.memory import ACTIVE_ISSUE_STATUSES
from app.modules.government.services.cleanliness import check_facility_low_usage
from app.modules.government.services.facilities import compute_condition_band


class OverviewService:
    def __init__(
        self,
        facility_repo: FacilityRepository,
        feedback_repo: FeedbackRepository,
        cleanliness_repo: CleanlinessRepository,
        issue_repo: IssueRepository,
        score_provider: FacilityScoreProvider,
        settings: GovernmentSettings,
        data_source: Literal["memory", "sql"] = "memory",
    ) -> None:
        self._facilities = facility_repo
        self._feedback = feedback_repo
        self._cleanliness = cleanliness_repo
        self._issues = issue_repo
        self._scores = score_provider
        self._settings = settings
        self._data_source = data_source

    def get_overview(self, now: datetime) -> OverviewStatistics:
        facilities = self._facilities.list()
        total_facilities = len(facilities)
        recommended = 0
        needing_attention = 0
        unscored = 0
        unverified = 0
        facilities_low_usage = 0
        facilities_cleanliness_unknown = 0

        for fac in facilities:
            if fac.verification_status != VerificationStatus.verified:
                unverified += 1
            score = self._scores.get_score(fac.id)
            band = compute_condition_band(score, self._settings)
            if band == ConditionBand.recommended:
                recommended += 1
            elif band == ConditionBand.attention:
                needing_attention += 1
            elif band == ConditionBand.unscored:
                unscored += 1

            low_usage, cleanliness_unknown = check_facility_low_usage(
                self._cleanliness, fac.id, now, self._settings
            )
            if low_usage:
                facilities_low_usage += 1
            if cleanliness_unknown:
                facilities_cleanliness_unknown += 1

        all_feedback = self._feedback.list(FeedbackFilterParams())
        pending_cutoff = now - timedelta(
            days=self._settings.PENDING_FEEDBACK_WINDOW_DAYS
        )
        positive_feedback_count = 0
        negative_feedback_count = 0
        pending_complaints = 0

        for item in all_feedback:
            if item.source != FeedbackSource.citizen_feedback:
                continue
            if item.sentiment == FeedbackSentiment.positive:
                positive_feedback_count += 1
            elif item.sentiment == FeedbackSentiment.negative:
                negative_feedback_count += 1
                if item.linked_issue_id is None and item.created_at >= pending_cutoff:
                    pending_complaints += 1

        all_issues = self._issues.list(IssueFilterParams())
        active_issues = 0
        escalated_issues = 0
        resolved_issues = 0
        alerts_cutoff = now - timedelta(hours=24)
        cleanliness_alerts_last_24h = 0

        for issue in all_issues:
            if issue.status in ACTIVE_ISSUE_STATUSES:
                active_issues += 1
            if issue.status == IssueStatus.escalated:
                escalated_issues += 1
            if issue.status == IssueStatus.resolved:
                resolved_issues += 1
            if (
                issue.type == IssueType.cleaning
                and issue.created_at >= alerts_cutoff
            ):
                cleanliness_alerts_last_24h += 1

        recent_cutoff = now - timedelta(days=self._settings.RECENT_INSPECTION_DAYS)
        recent_inspections = sum(
            1
            for insp in self._facilities.all_inspections()
            if insp.inspected_at >= recent_cutoff
        )

        return OverviewStatistics(
            total_facilities=total_facilities,
            recommended=recommended,
            needing_attention=needing_attention,
            unscored=unscored,
            unverified=unverified,
            pending_complaints=pending_complaints,
            active_issues=active_issues,
            escalated_issues=escalated_issues,
            resolved_issues=resolved_issues,
            recent_inspections=recent_inspections,
            positive_feedback_count=positive_feedback_count,
            negative_feedback_count=negative_feedback_count,
            cleanliness_alerts_last_24h=cleanliness_alerts_last_24h,
            facilities_low_usage=facilities_low_usage,
            facilities_cleanliness_unknown=facilities_cleanliness_unknown,
            generated_at=now,
            data_source=self._data_source,
        )

