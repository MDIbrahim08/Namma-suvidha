"""Request and response schemas for `/api/v1/government`.

OWNER: Ibrahim

Note on `triage`: Every `triage` / `triage_level` field in these schemas represents
a **government triage classification** (`urgent`/`high`/`normal`/`unranked`) for
ordering follow-up work. It is NOT a cleanliness score, NOT a facility score, and
NOT a substitute for Shubham's official scoring engine in `app.modules.intelligence`.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.modules.government.domain import (
    CitizenFeedbackItem,
    CleanlinessWindow,
    EvaluationSummary,
    FacilityDetail,
    FacilitySummary,
    MaintenanceDetectionSummary,
    MaintenanceIssue,
    NotificationRecord,
    OverviewStatistics,
    RepeatedComplaintCluster,
)
from app.modules.government.enums import IssueStatus, NotificationChannel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class FacilityFeedbackMeta(BaseModel):
    sentiment_breakdown: dict[str, int]
    cleanliness_windows: list[CleanlinessWindow]


class FacilityFeedbackResponse(PaginatedResponse[CitizenFeedbackItem]):
    meta: FacilityFeedbackMeta


class IssueTransitionRequest(BaseModel):
    to_status: IssueStatus
    note: str | None = Field(default=None, max_length=500)


class IssueNotifyRequest(BaseModel):
    channel: NotificationChannel = NotificationChannel.email


class EvaluateResponse(BaseModel):
    cleanliness: EvaluationSummary
    maintenance: MaintenanceDetectionSummary


__all__ = [
    "CitizenFeedbackItem",
    "CleanlinessWindow",
    "EvaluateResponse",
    "EvaluationSummary",
    "FacilityDetail",
    "FacilityFeedbackMeta",
    "FacilityFeedbackResponse",
    "FacilitySummary",
    "IssueNotifyRequest",
    "IssueTransitionRequest",
    "MaintenanceDetectionSummary",
    "MaintenanceIssue",
    "NotificationRecord",
    "OverviewStatistics",
    "PaginatedResponse",
    "RepeatedComplaintCluster",
]

