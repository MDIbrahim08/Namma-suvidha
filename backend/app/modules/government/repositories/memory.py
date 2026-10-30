"""In-memory repository implementations for Government Monitoring.

OWNER: Ibrahim

Starts completely EMPTY. Never loads fixture data at startup.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from app.modules.government.domain import (
    CitizenFeedbackItem,
    CleanlinessResponse,
    CleanlinessWindow,
    FacilityRecord,
    InspectionSummary,
    IssueAuditEntry,
    MaintenanceIssue,
    NotificationRecord,
    RepeatedComplaintCluster,
)
from app.modules.government.enums import (
    CleanlinessVerdict,
    FeedbackCategory,
    FeedbackSentiment,
    FeedbackSource,
    IssueStatus,
    IssueType,
    NotificationStatus,
)
from app.modules.government.exceptions import ResourceNotFoundError
from app.modules.government.interfaces import (
    FeedbackFilterParams,
    IssueFilterParams,
)


class InMemoryFacilityRepository:
    def __init__(self) -> None:
        self._facilities: dict[str, FacilityRecord] = {}
        self._inspections: dict[str, list[InspectionSummary]] = defaultdict(list)

    def clear(self) -> None:
        self._facilities.clear()
        self._inspections.clear()

    def seed_facility(self, facility: FacilityRecord) -> None:
        self._facilities[facility.id] = facility.model_copy(deep=True)

    def seed_inspection(self, inspection: InspectionSummary) -> None:
        self._inspections[inspection.facility_id].append(inspection.model_copy(deep=True))
        self._inspections[inspection.facility_id].sort(
            key=lambda item: item.inspected_at, reverse=True
        )

    def list(self) -> list[FacilityRecord]:
        return [
            self._facilities[fid].model_copy(deep=True)
            for fid in sorted(self._facilities.keys())
        ]

    def list_all_ids(self) -> list[str]:
        return sorted(self._facilities.keys())

    def get(self, facility_id: str) -> FacilityRecord | None:
        record = self._facilities.get(facility_id)
        return record.model_copy(deep=True) if record else None

    def latest_inspection(self, facility_id: str) -> InspectionSummary | None:
        items = self._inspections.get(facility_id, [])
        return items[0].model_copy(deep=True) if items else None

    def all_inspections(self) -> list[InspectionSummary]:
        out: list[InspectionSummary] = []
        for items in self._inspections.values():
            out.extend(item.model_copy(deep=True) for item in items)
        return out


class InMemoryFeedbackRepository:
    def __init__(self, facility_repo: InMemoryFacilityRepository | None = None) -> None:
        self._items: list[CitizenFeedbackItem] = []
        self._facility_repo = facility_repo

    def clear(self) -> None:
        self._items.clear()

    def seed_feedback(self, item: CitizenFeedbackItem) -> None:
        # Enforce citizen_feedback source invariant
        copy = item.model_copy(
            deep=True, update={"source": FeedbackSource.citizen_feedback}
        )
        self._items.append(copy)

    def list(self, filters: FeedbackFilterParams) -> list[CitizenFeedbackItem]:
        results: list[CitizenFeedbackItem] = []
        for item in self._items:
            if filters.facility_id and item.facility_id != filters.facility_id:
                continue
            if filters.ward and item.ward != filters.ward:
                continue
            if filters.category and item.category != filters.category:
                continue
            if filters.sentiment and item.sentiment != filters.sentiment:
                continue
            if filters.severity is not None and item.severity != filters.severity:
                continue
            if filters.channel and item.channel != filters.channel:
                continue
            if filters.since and item.created_at < filters.since:
                continue
            if filters.linked_to_issue is True and not item.linked_issue_id:
                continue
            if filters.linked_to_issue is False and item.linked_issue_id is not None:
                continue
            results.append(item.model_copy(deep=True))
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results

    def list_for_facility(
        self, facility_id: str, since: datetime | None = None
    ) -> list[CitizenFeedbackItem]:
        return self.list(FeedbackFilterParams(facility_id=facility_id, since=since))

    def repeated_clusters(
        self,
        now: datetime,
        window_days: int,
        min_count: int,
        min_reporters: int,
        facility_id: str | None = None,
    ) -> list[RepeatedComplaintCluster]:
        cutoff = now - timedelta(days=window_days)
        groups: dict[tuple[str, FeedbackCategory], list[CitizenFeedbackItem]] = defaultdict(
            list
        )
        for item in self._items:
            if item.source != FeedbackSource.citizen_feedback:
                continue
            if item.sentiment != FeedbackSentiment.negative:
                continue
            if item.created_at < cutoff or item.created_at > now:
                continue
            if facility_id and item.facility_id != facility_id:
                continue
            groups[(item.facility_id, item.category)].append(item)

        clusters: list[RepeatedComplaintCluster] = []
        for (fid, category), items in groups.items():
            if len(items) < min_count:
                continue
            reporters = {
                item.reporter_hash if item.reporter_hash else f"anon:{item.id}"
                for item in items
            }
            if len(reporters) < min_reporters:
                continue
            timestamps = [item.created_at for item in items]
            fac = self._facility_repo.get(fid) if self._facility_repo else None
            clusters.append(
                RepeatedComplaintCluster(
                    facility_id=fid,
                    facility_name=fac.name if fac else None,
                    ward=fac.ward if fac else items[0].ward,
                    category=category,
                    count=len(items),
                    distinct_reporters=len(reporters),
                    first_seen=min(timestamps),
                    last_seen=max(timestamps),
                )
            )
        clusters.sort(key=lambda c: (c.count, c.last_seen), reverse=True)
        return clusters


class InMemoryCleanlinessRepository:
    def __init__(self) -> None:
        self._responses: list[CleanlinessResponse] = []
        self._windows: list[CleanlinessWindow] = []

    def clear(self) -> None:
        self._responses.clear()
        self._windows.clear()

    def seed_response(self, response: CleanlinessResponse) -> None:
        self._responses.append(response.model_copy(deep=True))

    def responses_for_facility(
        self, facility_id: str, start: datetime, end: datetime
    ) -> list[CleanlinessResponse]:
        return [
            r.model_copy(deep=True)
            for r in self._responses
            if r.facility_id == facility_id and start <= r.created_at < end
        ]

    def count_responses(
        self, facility_id: str, start: datetime, end: datetime
    ) -> int:
        return sum(
            1
            for r in self._responses
            if r.facility_id == facility_id and start <= r.created_at < end
        )

    def save_window(self, window: CleanlinessWindow) -> CleanlinessWindow:
        copy = window.model_copy(deep=True)
        self._windows = [
            w
            for w in self._windows
            if not (
                w.facility_id == copy.facility_id
                and w.window_start == copy.window_start
            )
        ]
        self._windows.append(copy)
        self._windows.sort(key=lambda w: (w.window_start, w.facility_id), reverse=True)
        return copy.model_copy(deep=True)

    def latest_window(self, facility_id: str) -> CleanlinessWindow | None:
        facility_windows = [w for w in self._windows if w.facility_id == facility_id]
        if not facility_windows:
            return None
        facility_windows.sort(key=lambda w: w.window_start, reverse=True)
        return facility_windows[0].model_copy(deep=True)

    def window_exists(self, facility_id: str, window_start: datetime) -> bool:
        return any(
            w.facility_id == facility_id and w.window_start == window_start
            for w in self._windows
        )

    def list_windows(
        self,
        facility_id: str | None = None,
        since: datetime | None = None,
        verdict: CleanlinessVerdict | None = None,
    ) -> list[CleanlinessWindow]:
        out: list[CleanlinessWindow] = []
        for w in self._windows:
            if facility_id and w.facility_id != facility_id:
                continue
            if since and w.window_start < since:
                continue
            if verdict and w.verdict != verdict:
                continue
            out.append(w.model_copy(deep=True))
        out.sort(key=lambda w: (w.window_start, w.facility_id), reverse=True)
        return out


ACTIVE_ISSUE_STATUSES = {
    IssueStatus.open,
    IssueStatus.alert_sent,
    IssueStatus.acknowledged,
    IssueStatus.escalated,
}


class InMemoryIssueRepository:
    def __init__(self) -> None:
        self._issues: dict[str, MaintenanceIssue] = {}

    def clear(self) -> None:
        self._issues.clear()

    def create(self, issue: MaintenanceIssue) -> MaintenanceIssue:
        copy = issue.model_copy(deep=True)
        self._issues[copy.id] = copy
        return copy.model_copy(deep=True)

    def get(self, issue_id: str) -> MaintenanceIssue | None:
        issue = self._issues.get(issue_id)
        return issue.model_copy(deep=True) if issue else None

    def list(self, filters: IssueFilterParams) -> list[MaintenanceIssue]:
        out: list[MaintenanceIssue] = []
        for issue in self._issues.values():
            if filters.status and issue.status != filters.status:
                continue
            if filters.type and issue.type != filters.type:
                continue
            if filters.triage_level and issue.triage_level != filters.triage_level:
                continue
            if filters.ward and issue.ward != filters.ward:
                continue
            if filters.facility_id and issue.facility_id != filters.facility_id:
                continue
            out.append(issue.model_copy(deep=True))
        out.sort(key=lambda i: (i.created_at, i.id), reverse=True)
        return out

    def find_open(
        self,
        facility_id: str,
        issue_type: IssueType,
        category: FeedbackCategory | None = None,
    ) -> MaintenanceIssue | None:
        for issue in self._issues.values():
            if issue.facility_id != facility_id:
                continue
            if issue.type != issue_type:
                continue
            if issue.status not in ACTIVE_ISSUE_STATUSES:
                continue
            if category is not None and issue.category != category:
                continue
            return issue.model_copy(deep=True)
        return None

    def append_transition(
        self,
        issue_id: str,
        entry: IssueAuditEntry,
        new_status: IssueStatus,
    ) -> MaintenanceIssue:
        issue = self._issues.get(issue_id)
        if issue is None:
            raise ResourceNotFoundError(f"Issue '{issue_id}' not found")
        issue.history.append(entry.model_copy(deep=True))
        issue.status = new_status
        issue.updated_at = entry.timestamp
        return issue.model_copy(deep=True)

    def update_counters(
        self,
        issue_id: str,
        consecutive_negative_windows: int,
        verification_requested_at: datetime | None,
        updated_at: datetime,
    ) -> MaintenanceIssue:
        issue = self._issues.get(issue_id)
        if issue is None:
            raise ResourceNotFoundError(f"Issue '{issue_id}' not found")
        issue.consecutive_negative_windows = consecutive_negative_windows
        issue.verification_requested_at = verification_requested_at
        issue.updated_at = updated_at
        return issue.model_copy(deep=True)

    def attach_notification(
        self, issue_id: str, record: NotificationRecord
    ) -> MaintenanceIssue:
        issue = self._issues.get(issue_id)
        if issue is None:
            raise ResourceNotFoundError(f"Issue '{issue_id}' not found")
        issue.notifications.append(record.model_copy(deep=True))
        issue.updated_at = record.sent_at or record.created_at
        return issue.model_copy(deep=True)

    def update_notification_status(
        self,
        issue_id: str,
        notification_id: str,
        status: NotificationStatus,
        acknowledged_at: datetime | None = None,
    ) -> NotificationRecord | None:
        issue = self._issues.get(issue_id)
        if issue is None:
            return None
        for notif in issue.notifications:
            if notif.id == notification_id:
                notif.status = status
                if acknowledged_at is not None:
                    notif.acknowledged_at = acknowledged_at
                return notif.model_copy(deep=True)
        return None
