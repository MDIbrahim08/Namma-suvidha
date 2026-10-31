"""Government monitoring API routes (`/api/v1/government`).

OWNER: Ibrahim

Routes contain zero business logic: they validate query/body parameters,
call the Government service layer, and return typed schemas following the
Phase 0 envelope and pagination conventions.
"""

from datetime import datetime
from typing import Any, TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.modules.government.dependencies import (
    GovernmentServices,
    extract_actor_id,
    extract_roles,
    get_score_provider,
    get_services,
    require_government_user,
)
from app.modules.government.dev_fixtures import load_dev_fixtures
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
from app.modules.government.exceptions import GovernmentDomainError
from app.modules.government.interfaces import (
    FacilityFilterParams,
    FeedbackFilterParams,
    IssueFilterParams,
)
from app.schemas.government import (
    CitizenFeedbackItem,
    CleanlinessWindow,
    EvaluateResponse,
    FacilityDetail,
    FacilityFeedbackMeta,
    FacilityFeedbackResponse,
    FacilitySummary,
    GovernmentAuditRecord,
    IssueNotifyRequest,
    IssueTransitionRequest,
    MaintenanceIssue,
    NotificationRecord,
    OfficialContact,
    OverviewStatistics,
    PaginatedResponse,
    RepeatedComplaintCluster,
    StructuredIncidentReport,
)

router = APIRouter(
    prefix="/government",
    tags=["government"],
    dependencies=[Depends(require_government_user)],
)

T = TypeVar("T")


def _paginate(items: list[T], page: int, page_size: int) -> dict[str, Any]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _check_page_size(page_size: int, max_page_size: int) -> None:
    if page_size > max_page_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"page_size cannot exceed {max_page_size}",
        )


@router.get("/overview", response_model=OverviewStatistics)
def get_overview(
    services: GovernmentServices = Depends(get_services),
) -> OverviewStatistics:
    return services.overview.get_overview(services.clock.now())


@router.get("/facilities", response_model=PaginatedResponse[FacilitySummary])
def list_facilities(
    ward: str | None = None,
    verification_status: VerificationStatus | None = None,
    condition: ConditionBand | None = None,
    stale_only: bool = False,
    low_usage_only: bool = False,
    lat: float | None = Query(default=None, ge=-90.0, le=90.0),
    lng: float | None = Query(default=None, ge=-180.0, le=180.0),
    radius_m: float | None = Query(default=None, gt=0.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
    services: GovernmentServices = Depends(get_services),
) -> PaginatedResponse[FacilitySummary]:
    _check_page_size(page_size, services.settings.MAX_PAGE_SIZE)
    filters = FacilityFilterParams(
        ward=ward,
        verification_status=verification_status,
        condition=condition,
        stale_only=stale_only,
        low_usage_only=low_usage_only,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
    )
    items = services.facilities.list_facilities(filters, services.clock.now())
    return PaginatedResponse[FacilitySummary](**_paginate(items, page, page_size))


@router.get("/facilities/{facility_id}", response_model=FacilityDetail)
def get_facility_detail(
    facility_id: str,
    principal: Any = Depends(require_government_user),
    services: GovernmentServices = Depends(get_services),
) -> FacilityDetail:
    roles = extract_roles(principal) or {"government"}
    return services.facilities.get_facility_detail(
        facility_id, services.clock.now(), viewer_roles=roles
    )


@router.get(
    "/facilities/{facility_id}/feedback",
    response_model=FacilityFeedbackResponse,
)
def get_facility_feedback(
    facility_id: str,
    since: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
    services: GovernmentServices = Depends(get_services),
) -> FacilityFeedbackResponse:
    _check_page_size(page_size, services.settings.MAX_PAGE_SIZE)
    items, breakdown, windows = services.feedback.list_facility_feedback_with_meta(
        facility_id=facility_id,
        since=since,
        now=services.clock.now(),
    )
    paged = _paginate(items, page, page_size)
    return FacilityFeedbackResponse(
        **paged,
        meta=FacilityFeedbackMeta(
            sentiment_breakdown=breakdown,
            cleanliness_windows=windows,
        ),
    )


@router.get("/feedback", response_model=PaginatedResponse[CitizenFeedbackItem])
def list_feedback(
    facility_id: str | None = None,
    ward: str | None = None,
    category: FeedbackCategory | None = None,
    sentiment: FeedbackSentiment | None = None,
    severity: int | None = Query(default=None, ge=1, le=5),
    channel: FeedbackChannel | None = None,
    since: datetime | None = None,
    linked_to_issue: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
    services: GovernmentServices = Depends(get_services),
) -> PaginatedResponse[CitizenFeedbackItem]:
    _check_page_size(page_size, services.settings.MAX_PAGE_SIZE)
    filters = FeedbackFilterParams(
        facility_id=facility_id,
        ward=ward,
        category=category,
        sentiment=sentiment,
        severity=severity,
        channel=channel,
        since=since,
        linked_to_issue=linked_to_issue,
    )
    items = services.feedback.list_feedback(filters, services.clock.now())
    return PaginatedResponse[CitizenFeedbackItem](**_paginate(items, page, page_size))


@router.get(
    "/feedback/repeated",
    response_model=PaginatedResponse[RepeatedComplaintCluster],
)
def list_repeated_complaints(
    facility_id: str | None = None,
    ward: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
    services: GovernmentServices = Depends(get_services),
) -> PaginatedResponse[RepeatedComplaintCluster]:
    _check_page_size(page_size, services.settings.MAX_PAGE_SIZE)
    clusters = services.feedback.repeated_clusters(
        now=services.clock.now(), facility_id=facility_id, ward=ward
    )
    return PaginatedResponse[RepeatedComplaintCluster](
        **_paginate(clusters, page, page_size)
    )


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate_cleanliness_and_maintenance(
    principal: Any = Depends(require_government_user),
    services: GovernmentServices = Depends(get_services),
) -> EvaluateResponse:
    now = services.clock.now()
    actor_id = extract_actor_id(principal)
    clean_summary = services.cleanliness.evaluate(now=now, actor_id=actor_id)
    maint_summary = services.issues.detect_maintenance(now=now, actor_id=actor_id)
    return EvaluateResponse(cleanliness=clean_summary, maintenance=maint_summary)


@router.get(
    "/cleanliness/windows",
    response_model=PaginatedResponse[CleanlinessWindow],
)
def list_cleanliness_windows(
    facility_id: str | None = None,
    since: datetime | None = None,
    verdict: CleanlinessVerdict | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
    services: GovernmentServices = Depends(get_services),
) -> PaginatedResponse[CleanlinessWindow]:
    _check_page_size(page_size, services.settings.MAX_PAGE_SIZE)
    windows = services.repos.cleanliness.list_windows(
        facility_id=facility_id, since=since, verdict=verdict
    )
    return PaginatedResponse[CleanlinessWindow](**_paginate(windows, page, page_size))


@router.get("/issues", response_model=PaginatedResponse[MaintenanceIssue])
def list_issues(
    status: IssueStatus | None = None,
    type: IssueType | None = None,
    triage_level: TriageLevel | None = None,
    ward: str | None = None,
    facility_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
    services: GovernmentServices = Depends(get_services),
) -> PaginatedResponse[MaintenanceIssue]:
    _check_page_size(page_size, services.settings.MAX_PAGE_SIZE)
    filters = IssueFilterParams(
        status=status,
        type=type,
        triage_level=triage_level,
        ward=ward,
        facility_id=facility_id,
    )
    issues = services.issues.list_issues(filters)
    return PaginatedResponse[MaintenanceIssue](**_paginate(issues, page, page_size))


@router.get("/issues/{issue_id}", response_model=MaintenanceIssue)
def get_issue_detail(
    issue_id: str,
    services: GovernmentServices = Depends(get_services),
) -> MaintenanceIssue:
    return services.issues.get_issue(issue_id)


@router.post("/issues/{issue_id}/notify", response_model=NotificationRecord)
def notify_issue_operator(
    issue_id: str,
    body: IssueNotifyRequest | None = Body(default=None),
    principal: Any = Depends(require_government_user),
    services: GovernmentServices = Depends(get_services),
) -> NotificationRecord:
    req = body or IssueNotifyRequest()
    actor_id = extract_actor_id(principal)
    return services.notifications.send_alert(
        issue_id,
        actor_id=actor_id,
        now=services.clock.now(),
        channel=req.channel,
    )


@router.post("/issues/{issue_id}/transition", response_model=MaintenanceIssue)
def transition_issue_status(
    issue_id: str,
    body: IssueTransitionRequest,
    principal: Any = Depends(require_government_user),
    services: GovernmentServices = Depends(get_services),
) -> MaintenanceIssue:
    actor_id = extract_actor_id(principal)
    now = services.clock.now()
    if body.to_status == IssueStatus.acknowledged:
        return services.notifications.acknowledge(
            issue_id, actor_id=actor_id, note=body.note, now=now
        )
    if body.to_status == IssueStatus.resolved:
        return services.notifications.resolve(
            issue_id, actor_id=actor_id, note=body.note or "Resolved by authority", now=now
        )
    return services.issues.transition_issue(
        issue_id,
        to_status=body.to_status,
        actor_id=actor_id,
        note=body.note,
        now=now,
    )


@router.get("/incidents/{issue_id}/report", response_model=StructuredIncidentReport)
def get_incident_report(
    issue_id: str,
    services: GovernmentServices = Depends(get_services),
) -> StructuredIncidentReport:
    """Retrieve the full structured 11-point government incident report."""
    issue = services.issues.get_issue(issue_id)
    return services.notifications.generate_incident_report(
        issue=issue, now=services.clock.now()
    )


@router.post("/incidents/escalate-overdue", response_model=list[NotificationRecord])
def escalate_overdue_incidents(
    principal: Any = Depends(require_government_user),
    services: GovernmentServices = Depends(get_services),
) -> list[NotificationRecord]:
    """Scan and trigger automated escalation notifications for issues exceeding the response deadline."""
    actor_id = extract_actor_id(principal)
    return services.notifications.check_and_escalate_overdue_issues(
        now=services.clock.now(), actor_id=actor_id
    )


@router.get("/audit/records", response_model=list[GovernmentAuditRecord])
def list_audit_records(
    incident_id: str | None = None,
    event_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    services: GovernmentServices = Depends(get_services),
) -> list[GovernmentAuditRecord]:
    """Internal audit logs of incident creation, notification generation, and delivery status."""
    return services.notifications.list_audit_records(
        incident_id=incident_id, event_type=event_type, limit=limit
    )


@router.get("/contacts", response_model=list[OfficialContact])
def list_official_contacts(
    services: GovernmentServices = Depends(get_services),
) -> list[OfficialContact]:
    """List configured official contacts for BBMP zones, wards, and escalation authorities."""
    return services.notifications._contacts.list_contacts(active_only=False)


@router.post("/_dev/load-fixtures", include_in_schema=False)
def dev_load_fixtures(
    app_settings: Settings = Depends(get_settings),
    services: GovernmentServices = Depends(get_services),
) -> dict[str, object]:
    if (
        app_settings.APP_ENV != "development"
        or not services.settings.DEV_FIXTURES_ENABLED
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not Found"
        )
    score_provider = get_score_provider()
    return load_dev_fixtures(
        repos=services.repos,
        score_provider=score_provider,
        now=services.clock.now(),
        window_minutes=services.settings.CLEAN_WINDOW_MINUTES,
    )


__all__ = ["GovernmentDomainError", "router"]
