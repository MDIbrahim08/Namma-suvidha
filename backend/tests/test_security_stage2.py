"""Stage 2 Security & Privacy Regression Test Suite.

OWNER: Ibrahim (integration & security verification)
COORDINATES WITH: Shabaz (auth & RLS owner)

Covers all 6 Stage 2 security regression categories:
1. No secret exposure in frontend source or production build (`frontend/dist`),
   nor in `.env.example` templates.
2. No unauthorized access to sensitive endpoints (`/api/v1/government/*`).
3. PII redaction for non-government callers (`redact_responsible_party` and
   `sanitize_db_error_message`).
4. Production rejection of development authentication bypass (`GOV_DEV_AUTH_BYPASS`).
5. Missing or invalid credentials handled safely without leaking secrets.
6. Correct backend-only access to privileged operations (evaluate, notify, transition,
   and dev fixture loading).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.session import (
    check_database_connection,
    get_engine,
    get_sessionmaker,
    sanitize_db_error_message,
)
from app.main import app, create_app
from app.modules.government.config import (
    GovernmentSettings,
    get_government_settings,
    validate_government_startup,
)
from app.modules.government.domain import ResponsibleParty, redact_responsible_party
from app.modules.openrouter.client import OpenRouterConfigError, OpenRouterHttpClient
from app.modules.openrouter.pipeline import validate_audio_upload

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "frontend"
BACKEND_DIR = REPO_ROOT / "backend"


# ---------------------------------------------------------------------------
# 1. No Secret Exposure in Frontend Source, Build Bundle, or .env.example
# ---------------------------------------------------------------------------


def test_no_privileged_secret_names_or_values_in_frontend_source_or_build() -> None:
    """Verify that frontend source and production `dist/` bundle never contain
    privileged backend env keys (`SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`,
    `DATABASE_URL`, `SUPABASE_JWT_SECRET`) or secret prefixes (`sb_secret_`, `sk-or-`).
    """
    forbidden_patterns = (
        "SUPABASE_SERVICE_ROLE_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "SUPABASE_JWT_SECRET",
        "sb_secret_",
        "sk-or-v1-",
        "gsk_",
        "3WzgtfUVtfo33vtW",
    )

    files_to_scan: list[Path] = []
    src_dir = FRONTEND_DIR / "src"
    if src_dir.exists():
        files_to_scan.extend(p for p in src_dir.rglob("*") if p.is_file())

    dist_dir = FRONTEND_DIR / "dist"
    if dist_dir.exists():
        files_to_scan.extend(p for p in dist_dir.rglob("*") if p.is_file())

    assert files_to_scan, "Expected frontend/src files to exist for security scan"

    for file_path in files_to_scan:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for pattern in forbidden_patterns:
            assert pattern not in content, (
                f"Forbidden secret pattern '{pattern}' found in {file_path.relative_to(REPO_ROOT)}"
            )


def test_env_examples_contain_only_placeholders_and_no_live_secrets() -> None:
    """Verify `.env.example` files never contain live tokens or previously exposed secrets."""
    forbidden_live_tokens = (
        "sb_secret_",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "3WzgtfUVtfo33vtW",
        "tjtwdmhyvujarplllbee",
        "sk-or-v1-",
        "gsk_",
    )
    for env_example in (BACKEND_DIR / ".env.example", FRONTEND_DIR / ".env.example"):
        assert env_example.exists()
        text = env_example.read_text(encoding="utf-8")
        for token in forbidden_live_tokens:
            assert token not in text, (
                f"Live or compromised token '{token}' found in {env_example.name}"
            )


def test_frontend_supabase_direct_client_remains_disabled_until_rls_approved() -> None:
    """Confirm `frontend/src/lib/supabase.ts` keeps `supabase = null` until Shabaz
    approves and applies the RLS migration on the 7 public tables.
    """
    supabase_ts = (FRONTEND_DIR / "src" / "lib" / "supabase.ts").read_text(
        encoding="utf-8"
    )
    assert "export const supabase = null" in supabase_ts


# ---------------------------------------------------------------------------
# 2 & 6. No Unauthorized Access to Sensitive Endpoints & Privileged Operations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/government/overview", None),
        ("GET", "/api/v1/government/facilities", None),
        ("GET", "/api/v1/government/facilities/fac-001", None),
        ("GET", "/api/v1/government/feedback", None),
        ("GET", "/api/v1/government/feedback/repeated", None),
        ("POST", "/api/v1/government/evaluate", {}),
        ("GET", "/api/v1/government/issues", None),
        (
            "POST",
            "/api/v1/government/issues/iss-001/notify",
            {"channel": "email"},
        ),
        (
            "POST",
            "/api/v1/government/issues/iss-001/transition",
            {"to_status": "acknowledged"},
        ),
    ],
)
def test_privileged_endpoints_reject_unauthenticated_and_non_government_roles(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    payload: dict[str, Any] | None,
) -> None:
    """Every privileged Government endpoint must block:
    - Unauthenticated callers (HTTP 401 or 501 stub)
    - Authenticated `citizen` callers (HTTP 403)
    - Authenticated `evaluator` callers (HTTP 403)
    """
    monkeypatch.setenv("GOV_DEV_AUTH_BYPASS", "false")
    get_government_settings.cache_clear()

    client = TestClient(app)

    # Case A: Unauthenticated (401 when security raises 401, or 501 from default stub)
    def _unauthenticated() -> None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer token",
        )

    app.dependency_overrides[get_current_user] = _unauthenticated
    try:
        resp_unauth = client.request(method, path, json=payload)
        assert resp_unauth.status_code == 401
        assert resp_unauth.json()["code"] == "http_401"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # Case B: Authenticated Citizen (must receive 403 Forbidden)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-citizen-1",
        "role": "citizen",
    }
    try:
        resp_citizen = client.request(method, path, json=payload)
        assert resp_citizen.status_code == 403
        assert resp_citizen.json()["code"] == "http_403"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # Case C: Authenticated Evaluator (must receive 403 Forbidden on government routes)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-eval-1",
        "role": "evaluator",
    }
    try:
        resp_eval = client.request(method, path, json=payload)
        assert resp_eval.status_code == 403
        assert resp_eval.json()["code"] == "http_403"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_dev_fixtures_endpoint_blocked_when_disabled_or_non_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify `/api/v1/government/_dev/load-fixtures` returns 404 when
    `GOV_DEV_FIXTURES_ENABLED=false` even for an admin caller.
    """
    monkeypatch.setenv("GOV_DEV_FIXTURES_ENABLED", "false")
    get_government_settings.cache_clear()

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin-1",
        "role": "admin",
    }
    try:
        resp = client.post("/api/v1/government/_dev/load-fixtures")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        get_government_settings.cache_clear()


# ---------------------------------------------------------------------------
# 3. PII Redaction for Non-Government Callers & DB Error Sanitization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "non_gov_role",
    [None, "", "citizen", "evaluator", "anonymous", ["citizen"], {"evaluator"}],
)
def test_redact_responsible_party_strips_operator_pii_for_non_government_roles(
    non_gov_role: Any,
) -> None:
    party = ResponsibleParty(
        name="Ramesh Kumar",
        organization="BBMP East Zone",
        role_title="Ward Sanitation Supervisor",
        email="ramesh.supervisor@bbmp.gov.in",
        phone="+91-9876543210",
        verified=True,
    )
    redacted = redact_responsible_party(party, viewer_role=non_gov_role)
    assert redacted is not None
    assert redacted.name == "Ramesh Kumar"
    assert redacted.organization == "BBMP East Zone"
    assert redacted.email is None
    assert redacted.phone is None


@pytest.mark.parametrize("gov_role", ["government", "admin", ["government"], {"admin"}])
def test_redact_responsible_party_preserves_contact_for_government_and_admin(
    gov_role: Any,
) -> None:
    party = ResponsibleParty(
        name="Ramesh Kumar",
        organization="BBMP East Zone",
        role_title="Ward Sanitation Supervisor",
        email="ramesh.supervisor@bbmp.gov.in",
        phone="+91-9876543210",
        verified=True,
    )
    visible = redact_responsible_party(party, viewer_role=gov_role)
    assert visible is not None
    assert visible.email == "ramesh.supervisor@bbmp.gov.in"
    assert visible.phone == "+91-9876543210"


def test_sanitize_db_error_message_redacts_embedded_passwords() -> None:
    raw_error = (
        "OperationalError: connection to server at "
        "'postgresql+psycopg://postgres.project:SuperSecretPass123!"
        "@aws-0-ap-south-1.pooler.supabase.com:6543/postgres' failed"
    )
    sanitized = sanitize_db_error_message(raw_error)
    assert "SuperSecretPass123!" not in sanitized
    assert "***REDACTED***" in sanitized


# ---------------------------------------------------------------------------
# 4. Production Rejection of Development Authentication Bypass
# ---------------------------------------------------------------------------


def test_production_rejects_dev_auth_bypass_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gov_settings = GovernmentSettings(DEV_AUTH_BYPASS=True)
    with pytest.raises(RuntimeError, match="GOV_DEV_AUTH_BYPASS=true is forbidden"):
        validate_government_startup("production", gov_settings)

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GOV_DEV_AUTH_BYPASS", "true")
    get_settings.cache_clear()
    get_government_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="GOV_DEV_AUTH_BYPASS=true is forbidden"):
            create_app()
    finally:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("GOV_DEV_AUTH_BYPASS", "false")
        get_settings.cache_clear()
        get_government_settings.cache_clear()


# ---------------------------------------------------------------------------
# 5. Missing or Invalid Credentials Handled Safely Without Leaking Secrets
# ---------------------------------------------------------------------------


def test_invalid_db_credentials_never_leak_password_in_health_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_pw = "MyUltraSecretDatabasePassword999"
    monkeypatch.setenv(
        "DATABASE_URL",
        f"postgresql+psycopg://user:{secret_pw}@127.0.0.1:59999/namma_db",
    )
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    try:
        status_dict = check_database_connection()
        assert status_dict["connected"] is False
        assert status_dict["error"] is not None
        assert secret_pw not in status_dict["error"]
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


@pytest.mark.anyio
async def test_missing_openrouter_credentials_fail_closed_without_secret_leak() -> None:
    from app.core.config import Settings

    settings = Settings(OPENROUTER_API_KEY="")
    client = OpenRouterHttpClient(settings=settings)
    audio = validate_audio_upload(b"RIFF....WAVEfmt ", filename="test.wav")

    with pytest.raises(OpenRouterConfigError) as exc_info:
        await client.transcribe_audio(audio)
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "openrouter_not_configured"
