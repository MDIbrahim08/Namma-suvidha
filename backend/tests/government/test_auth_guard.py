"""Authentication guard and development bypass tests for all 12 government endpoints."""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.main import create_app
from app.modules.government.config import (
    GovernmentSettings,
    get_government_settings,
    validate_government_startup,
)
from app.modules.government.dependencies import extract_roles

ALL_GOVERNMENT_ROUTES: list[tuple[str, str, dict[str, object] | None]] = [
    ("GET", "/api/v1/government/overview", None),
    ("GET", "/api/v1/government/facilities", None),
    ("GET", "/api/v1/government/facilities/fac-1", None),
    ("GET", "/api/v1/government/facilities/fac-1/feedback", None),
    ("GET", "/api/v1/government/feedback", None),
    ("GET", "/api/v1/government/feedback/repeated", None),
    ("POST", "/api/v1/government/evaluate", None),
    ("GET", "/api/v1/government/cleanliness/windows", None),
    ("GET", "/api/v1/government/issues", None),
    ("GET", "/api/v1/government/issues/iss-1", None),
    ("POST", "/api/v1/government/issues/iss-1/notify", None),
    (
        "POST",
        "/api/v1/government/issues/iss-1/transition",
        {"to_status": "acknowledged", "note": "Ack"},
    ),
]


@pytest.mark.parametrize(("method", "path", "payload"), ALL_GOVERNMENT_ROUTES)
def test_all_routes_reject_unauthenticated_principal(
    method: str, path: str, payload: dict[str, object] | None
) -> None:
    """With Phase 0's 501 stub on `get_current_user`, every route must return non-2xx (501)."""
    app = create_app()
    with TestClient(app) as client:
        response = client.request(method, path, json=payload)
    assert response.status_code == 501
    assert response.json()["code"] == "http_501"


@pytest.mark.parametrize(("method", "path", "payload"), ALL_GOVERNMENT_ROUTES)
def test_all_routes_reject_citizen_role_with_403(
    method: str, path: str, payload: dict[str, object] | None
) -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "cit-1",
        "roles": ["citizen"],
    }
    with TestClient(app) as client:
        response = client.request(method, path, json=payload)
    assert response.status_code == 403
    assert response.json()["code"] == "http_403"


def test_government_role_passes_guard(gov_client: TestClient) -> None:
    response = gov_client.get("/api/v1/government/overview")
    assert response.status_code == 200


def test_dev_auth_bypass_refused_in_production() -> None:
    gov_settings = GovernmentSettings(DEV_AUTH_BYPASS=True)
    with pytest.raises(RuntimeError, match="GOV_DEV_AUTH_BYPASS=true is forbidden"):
        validate_government_startup("production", gov_settings)


def test_dev_auth_bypass_active_in_development_sets_header_and_logs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(APP_ENV="development")
    app.dependency_overrides[get_government_settings] = lambda: GovernmentSettings(
        DEV_AUTH_BYPASS=True
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/government/overview")
    assert response.status_code == 200
    assert response.headers.get("X-Dev-Auth-Bypass") == "true"
    captured = capsys.readouterr()
    assert "GOVERNMENT AUTH BYPASS ACTIVE" in captured.out


def test_extract_roles_adapter_orders_sources() -> None:
    @dataclass
    class ObjWithRoles:
        roles: list[str]

    @dataclass
    class ObjWithRole:
        role: str

    assert extract_roles(ObjWithRoles(roles=["Government"])) == {"government"}
    assert extract_roles(ObjWithRole(role="Admin")) == {"admin"}
    assert extract_roles({"roles": ["government", "evaluator"]}) == {
        "government",
        "evaluator",
    }
    assert extract_roles({"role": "government"}) == {"government"}
    assert extract_roles({"app_metadata": {"roles": ["admin"]}}) == {"admin"}
    assert extract_roles(None) == set()
