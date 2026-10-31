"""Domain models for Platform Audit Logging, Admin Overview, and Analytics.

OWNER: Internal Admin Audit & Analytics Module
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PlatformAuditEvent(BaseModel):
    """Immutable audit event representing significant platform activity."""

    event_id: str
    event_type: str  # e.g. feedback.submitted, inspection.completed, etc.
    description: str
    related_toilet_id: str | None = None
    toilet_name: str | None = None
    timestamp: datetime
    severity: Literal["critical", "high", "medium", "low", "info"] = "info"
    actor: str  # e.g. citizen:anon, volunteer:INF-CSR-2026-101, system:ai-classifier, admin:root
    status: Literal["success", "failed", "pending", "escalated", "resolved"] = "success"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdminDashboardSummary(BaseModel):
    """Real-time summary counts across all database entities."""

    total_toilets: int = 0
    total_feedback: int = 0
    total_inspections: int = 0
    total_reported_issues: int = 0
    pending_maintenance_tickets: int = 0
    notifications_sent: int = 0
    resolved_issues: int = 0
    last_updated: datetime


class FeedbackAnalytics(BaseModel):
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    total_count: int = 0
    sentiment_distribution: dict[str, int] = Field(default_factory=dict)
    submissions_over_time: list[dict[str, Any]] = Field(default_factory=list)
    top_reported_issues: list[dict[str, Any]] = Field(default_factory=list)


class FacilityAnalytics(BaseModel):
    total_facilities: int = 0
    recommended_count: int = 0
    needs_attention_count: int = 0
    excluded_count: int = 0
    score_distribution: dict[str, int] = Field(default_factory=dict)
    top_complaint_facilities: list[dict[str, Any]] = Field(default_factory=list)


class InspectionAnalytics(BaseModel):
    total_inspections: int = 0
    verified_pass_count: int = 0
    issue_flagged_count: int = 0
    inspections_over_time: list[dict[str, Any]] = Field(default_factory=list)
    issues_identified: dict[str, int] = Field(default_factory=dict)


class GovernmentResponseAnalytics(BaseModel):
    notifications_sent: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    pending_tickets: int = 0
    acknowledged_tickets: int = 0
    resolved_tickets: int = 0
    escalations_triggered: int = 0
    tickets_over_time: list[dict[str, Any]] = Field(default_factory=list)


class PaginatedAuditLogsResponse(BaseModel):
    items: list[PlatformAuditEvent]
    total: int
    page: int
    page_size: int

