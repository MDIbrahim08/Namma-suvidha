"""Admin Dashboard, Audit Logging & Analytics API endpoints (`/api/v1/admin`).

OWNER: Internal Admin Audit & Analytics Module

Provides endpoints for:
1. Dashboard summary cards (toilets, feedback, inspections, tickets, notifications, resolved issues).
2. Audit logs listing and multi-criteria filtering with search.
3. Feedback analytics (sentiment distribution, timelines, top categories).
4. Facility analytics (condition bands, score distribution, complaint hotspots).
5. Inspection analytics (completed audits, defect checklists).
6. Government response analytics (delivery success/failure, ticket pipeline, escalations).
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, status

from app.modules.admin.dependencies import require_admin_user
from app.modules.admin.domain import (
    AdminDashboardSummary,
    FacilityAnalytics,
    FeedbackAnalytics,
    GovernmentResponseAnalytics,
    InspectionAnalytics,
    PaginatedAuditLogsResponse,
    PlatformAuditEvent,
)
from app.modules.admin.repository import PlatformAuditRepository, get_platform_audit_repository
from app.modules.admin.service import AdminAnalyticsService, get_admin_analytics_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_user)],
)


@router.get("/dashboard/summary", response_model=AdminDashboardSummary)
def get_dashboard_summary(
    service: AdminAnalyticsService = Depends(get_admin_analytics_service),
) -> AdminDashboardSummary:
    """Retrieve real-time summary KPI metrics aggregated from actual platform data."""
    return service.get_dashboard_summary()


@router.get("/audit-logs", response_model=PaginatedAuditLogsResponse)
def list_audit_logs(
    event_type: str | None = Query(default=None, description="Filter by event type prefix or exact match"),
    severity: str | None = Query(default=None, description="Filter by severity: critical, high, medium, low, info"),
    status: str | None = Query(default=None, description="Filter by status: success, failed, pending, escalated, resolved"),
    search: str | None = Query(default=None, description="Search keyword in description, actor, or facility name"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: PlatformAuditRepository = Depends(get_platform_audit_repository),
) -> PaginatedAuditLogsResponse:
    """List immutable platform audit logs in reverse chronological order with filtering."""
    offset = (page - 1) * page_size
    items, total = repo.list_events(
        event_type=event_type,
        severity=severity,
        status=status,
        search_query=search,
        limit=page_size,
        offset=offset,
    )
    return PaginatedAuditLogsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/audit-logs", response_model=PlatformAuditEvent, status_code=status.HTTP_201_CREATED)
def record_audit_event(
    event: PlatformAuditEvent = Body(...),
    repo: PlatformAuditRepository = Depends(get_platform_audit_repository),
) -> PlatformAuditEvent:
    """Append a new platform audit event (internal operation)."""
    return repo.append(event)


@router.get("/analytics/feedback", response_model=FeedbackAnalytics)
def get_feedback_analytics(
    service: AdminAnalyticsService = Depends(get_admin_analytics_service),
) -> FeedbackAnalytics:
    """Retrieve feedback sentiment distribution, volume timelines, and frequent complaint categories."""
    return service.get_feedback_analytics()


@router.get("/analytics/facilities", response_model=FacilityAnalytics)
def get_facility_analytics(
    service: AdminAnalyticsService = Depends(get_admin_analytics_service),
) -> FacilityAnalytics:
    """Retrieve facility condition bands, score distributions, and complaint hot-spots."""
    return service.get_facility_analytics()


@router.get("/analytics/inspections", response_model=InspectionAnalytics)
def get_inspection_analytics(
    service: AdminAnalyticsService = Depends(get_admin_analytics_service),
) -> InspectionAnalytics:
    """Retrieve physical inspection audit trends and checklist defect breakdowns."""
    return service.get_inspection_analytics()


@router.get("/analytics/government", response_model=GovernmentResponseAnalytics)
def get_government_response_analytics(
    service: AdminAnalyticsService = Depends(get_admin_analytics_service),
) -> GovernmentResponseAnalytics:
    """Retrieve government response stats: notification delivery, ticket pipeline, and escalations."""
    return service.get_government_response_analytics()

