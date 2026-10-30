"""Repository, provider, and Clock protocols for Government Monitoring.

OWNER: Ibrahim

Services depend exclusively on these protocols so the storage layer can switch
from `memory` to `sql` once Shubham's ORM models are merged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel

from app.modules.government.domain import (
    CitizenFeedbackItem,
    CleanlinessResponse,
    CleanlinessWindow,
    FacilityRecord,
    InspectionSummary,
    IssueAuditEntry,
    MaintenanceIssue,
    NotificationRecord,
    OfficialScore,
    RepeatedComplaintCluster,
)
from app.modules.government.enums import (
    CleanlinessVerdict,
    ConditionBand,
    FeedbackCategory,
    FeedbackChannel,
    FeedbackSentiment,
    IssueStatus,
    IssueType,
    TriageLevel,
    VerificationStatus,
)


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20


class FacilityFilterParams(BaseModel):
    ward: str | None = None
    verification_status: VerificationStatus | None = None
    condition: ConditionBand | None = None
    stale_only: bool = False
    low_usage_only: bool = False
    lat: float | None = None
    lng: float | None = None
    radius_m: float | None = None


class FeedbackFilterParams(BaseModel):
    facility_id: str | None = None
    ward: str | None = None
    category: FeedbackCategory | None = None
    sentiment: FeedbackSentiment | None = None
    severity: int | None = None
    channel: FeedbackChannel | None = None
    since: datetime | None = None
    linked_to_issue: bool | None = None


class IssueFilterParams(BaseModel):
    status: IssueStatus | None = None
    type: IssueType | None = None
    triage_level: TriageLevel | None = None
    ward: str | None = None
    facility_id: str | None = None


class DeliveryResult(BaseModel):
    ok: bool
    provider_message: str
    sent_at: datetime | None = None


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        from datetime import UTC

        return datetime.now(UTC)


class FacilityRepository(Protocol):
    def list(self) -> list[FacilityRecord]: ...
    def list_all_ids(self) -> list[str]: ...
    def get(self, facility_id: str) -> FacilityRecord | None: ...
    def latest_inspection(self, facility_id: str) -> InspectionSummary | None: ...
    def all_inspections(self) -> list[InspectionSummary]: ...


class FeedbackRepository(Protocol):
    def list(self, filters: FeedbackFilterParams) -> list[CitizenFeedbackItem]: ...
    def list_for_facility(
        self, facility_id: str, since: datetime | None = None
    ) -> list[CitizenFeedbackItem]: ...
    def repeated_clusters(
        self,
        now: datetime,
        window_days: int,
        min_count: int,
        min_reporters: int,
        facility_id: str | None = None,
    ) -> list[RepeatedComplaintCluster]: ...


class CleanlinessRepository(Protocol):
    def responses_for_facility(
        self, facility_id: str, start: datetime, end: datetime
    ) -> list[CleanlinessResponse]: ...
    def count_responses(self, facility_id: str, start: datetime, end: datetime) -> int: ...
    def save_window(self, window: CleanlinessWindow) -> CleanlinessWindow: ...
    def latest_window(self, facility_id: str) -> CleanlinessWindow | None: ...
    def window_exists(self, facility_id: str, window_start: datetime) -> bool: ...
    def list_windows(
        self,
        facility_id: str | None = None,
        since: datetime | None = None,
        verdict: CleanlinessVerdict | None = None,
    ) -> list[CleanlinessWindow]: ...


class IssueRepository(Protocol):
    def create(self, issue: MaintenanceIssue) -> MaintenanceIssue: ...
    def get(self, issue_id: str) -> MaintenanceIssue | None: ...
    def list(self, filters: IssueFilterParams) -> list[MaintenanceIssue]: ...
    def find_open(
        self,
        facility_id: str,
        issue_type: IssueType,
        category: FeedbackCategory | None = None,
    ) -> MaintenanceIssue | None: ...
    def append_transition(
        self,
        issue_id: str,
        entry: IssueAuditEntry,
        new_status: IssueStatus,
    ) -> MaintenanceIssue: ...
    def update_counters(
        self,
        issue_id: str,
        consecutive_negative_windows: int,
        verification_requested_at: datetime | None,
        updated_at: datetime,
    ) -> MaintenanceIssue: ...
    def attach_notification(
        self, issue_id: str, record: NotificationRecord
    ) -> MaintenanceIssue: ...
    def update_notification_status(
        self,
        issue_id: str,
        notification_id: str,
        status: Any,
        acknowledged_at: datetime | None = None,
    ) -> NotificationRecord | None: ...


class FacilityScoreProvider(Protocol):
    def get_score(self, facility_id: str) -> OfficialScore | None: ...


class EmailProvider(Protocol):
    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        payload: dict[str, Any],
    ) -> DeliveryResult: ...
