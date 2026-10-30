"""FastAPI dependencies for Government Monitoring: auth guard and service container.

OWNER: Ibrahim (module wiring) / Shabaz (auth principal & `get_current_user`)
"""

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, Response, status

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.modules.government.config import (
    GovernmentSettings,
    get_government_settings,
    validate_government_startup,
)
from app.modules.government.interfaces import (
    Clock,
    EmailProvider,
    FacilityScoreProvider,
    SystemClock,
)
from app.modules.government.providers.email import TestEmailProvider
from app.modules.government.providers.scores import IntelligenceScoreProvider
from app.modules.government.repositories import RepositoryBundle, get_repository_bundle
from app.modules.government.services.cleanliness import CleanlinessService
from app.modules.government.services.facilities import FacilityService
from app.modules.government.services.feedback import FeedbackService
from app.modules.government.services.issues import IssueService
from app.modules.government.services.notifications import NotificationService
from app.modules.government.services.overview import OverviewService

logger = logging.getLogger("namma_suvidha.government.security")


def extract_roles(principal: Any) -> set[str]:
    """Extract role names from Shabaz's authenticated principal object or dict.

    Checks in order:
    1. attribute `roles`
    2. attribute `role`
    3. dict keys `roles` / `role`
    4. dict/attribute `app_metadata.roles`

    Shabaz to confirm or replace once `get_current_user` lands in Phase 1/2.
    """
    if principal is None:
        return set()

    def _normalise(val: Any) -> set[str]:
        if val is None:
            return set()
        if isinstance(val, str):
            return {val.strip().lower()} if val.strip() else set()
        if isinstance(val, list | tuple | set):
            return {str(item).strip().lower() for item in val if str(item).strip()}
        return set()

    if not isinstance(principal, dict):
        if hasattr(principal, "roles"):
            roles = _normalise(principal.roles)
            if roles:
                return roles
        if hasattr(principal, "role"):
            roles = _normalise(principal.role)
            if roles:
                return roles
        app_meta = getattr(principal, "app_metadata", None)
        if isinstance(app_meta, dict) and "roles" in app_meta:
            return _normalise(app_meta.get("roles"))
        if hasattr(app_meta, "roles"):
            return _normalise(app_meta.roles)
        return set()

    if "roles" in principal:
        roles = _normalise(principal.get("roles"))
        if roles:
            return roles
    if "role" in principal:
        roles = _normalise(principal.get("role"))
        if roles:
            return roles
    app_meta = principal.get("app_metadata")
    if isinstance(app_meta, dict) and "roles" in app_meta:
        return _normalise(app_meta.get("roles"))
    return set()


def extract_actor_id(principal: Any) -> str:
    if isinstance(principal, dict):
        for key in ("id", "sub", "user_id", "email"):
            if principal.get(key):
                return str(principal[key])
    for attr in ("id", "sub", "user_id", "email"):
        val = getattr(principal, attr, None)
        if val:
            return str(val)
    return "government-user"


def require_government_user(
    request: Request,
    response: Response,
    app_settings: Settings = Depends(get_settings),
    gov_settings: GovernmentSettings = Depends(get_government_settings),
) -> dict[str, Any] | Any:
    """Protect every `/api/v1/government` route.

    - In `development` with `GOV_DEV_AUTH_BYPASS=true`, logs a WARNING, sets
      `X-Dev-Auth-Bypass: true`, and returns a synthetic government principal.
    - Otherwise invokes Shabaz's `get_current_user` (respecting any FastAPI
      `dependency_overrides` configured by tests) and verifies role membership.
    """
    validate_government_startup(app_settings.APP_ENV, gov_settings)

    if gov_settings.DEV_AUTH_BYPASS and app_settings.APP_ENV == "development":
        logger.warning(
            "GOVERNMENT AUTH BYPASS ACTIVE — development only (path=%s)",
            request.url.path,
        )
        response.headers["X-Dev-Auth-Bypass"] = "true"
        return {
            "id": "dev-government-user",
            "roles": ["government"],
            "dev_bypass": True,
        }

    # Resolve get_current_user through app.dependency_overrides if present
    dep_fn = request.app.dependency_overrides.get(get_current_user, get_current_user)
    principal = dep_fn()

    roles = extract_roles(principal)
    allowed = {r.lower() for r in gov_settings.ALLOWED_ROLES}
    if not (roles & allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Government or admin role required to access this endpoint.",
        )
    return principal


@dataclass
class GovernmentServices:
    repos: RepositoryBundle
    settings: GovernmentSettings
    clock: Clock
    score_provider: FacilityScoreProvider
    email_provider: EmailProvider
    facilities: FacilityService
    overview: OverviewService
    feedback: FeedbackService
    issues: IssueService
    notifications: NotificationService
    cleanliness: CleanlinessService


_DEFAULT_CLOCK: Clock = SystemClock()
_DEFAULT_SCORE_PROVIDER = IntelligenceScoreProvider()
_DEFAULT_EMAIL_PROVIDER = TestEmailProvider()


def get_clock() -> Clock:
    return _DEFAULT_CLOCK


def get_score_provider() -> IntelligenceScoreProvider:
    return _DEFAULT_SCORE_PROVIDER


def get_email_provider() -> TestEmailProvider:
    return _DEFAULT_EMAIL_PROVIDER


def build_government_services(
    *,
    repos: RepositoryBundle | None = None,
    gov_settings: GovernmentSettings | None = None,
    clock: Clock | None = None,
    score_provider: FacilityScoreProvider | None = None,
    email_provider: EmailProvider | None = None,
) -> GovernmentServices:
    settings = gov_settings or get_government_settings()
    bundle = repos or get_repository_bundle(settings.REPOSITORY_BACKEND)
    clk = clock or get_clock()
    scores = score_provider or get_score_provider()
    email = email_provider or get_email_provider()

    facilities_svc = FacilityService(
        facility_repo=bundle.facilities,
        feedback_repo=bundle.feedback,
        cleanliness_repo=bundle.cleanliness,
        issue_repo=bundle.issues,
        score_provider=scores,
        settings=settings,
    )
    overview_svc = OverviewService(
        facility_repo=bundle.facilities,
        feedback_repo=bundle.feedback,
        cleanliness_repo=bundle.cleanliness,
        issue_repo=bundle.issues,
        score_provider=scores,
        settings=settings,
        data_source=bundle.data_source,
    )
    feedback_svc = FeedbackService(
        facility_repo=bundle.facilities,
        feedback_repo=bundle.feedback,
        cleanliness_repo=bundle.cleanliness,
        settings=settings,
    )
    issues_svc = IssueService(
        issue_repo=bundle.issues,
        facility_repo=bundle.facilities,
        feedback_repo=bundle.feedback,
        cleanliness_repo=bundle.cleanliness,
        score_provider=scores,
        settings=settings,
    )
    notifications_svc = NotificationService(
        issue_repo=bundle.issues,
        facility_repo=bundle.facilities,
        feedback_repo=bundle.feedback,
        cleanliness_repo=bundle.cleanliness,
        score_provider=scores,
        email_provider=email,
        issue_service=issues_svc,
        settings=settings,
    )
    cleanliness_svc = CleanlinessService(
        facility_repo=bundle.facilities,
        cleanliness_repo=bundle.cleanliness,
        issue_repo=bundle.issues,
        settings=settings,
        issue_service=issues_svc,
        notification_service=notifications_svc,
    )

    return GovernmentServices(
        repos=bundle,
        settings=settings,
        clock=clk,
        score_provider=scores,
        email_provider=email,
        facilities=facilities_svc,
        overview=overview_svc,
        feedback=feedback_svc,
        issues=issues_svc,
        notifications=notifications_svc,
        cleanliness=cleanliness_svc,
    )


def get_services(
    gov_settings: GovernmentSettings = Depends(get_government_settings),
    clock: Clock = Depends(get_clock),
    score_provider: FacilityScoreProvider = Depends(get_score_provider),
    email_provider: EmailProvider = Depends(get_email_provider),
) -> GovernmentServices:
    return build_government_services(
        gov_settings=gov_settings,
        clock=clock,
        score_provider=score_provider,
        email_provider=email_provider,
    )
