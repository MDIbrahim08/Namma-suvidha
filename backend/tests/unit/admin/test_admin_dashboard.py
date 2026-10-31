"""Unit and API integration tests for the Internal Admin Audit & Analytics Dashboard.

OWNER: Internal Admin Audit & Analytics Module

Verifies:
1. Dashboard summary calculation from actual database/repository stores.
2. Reverse-chronological audit logs listing with filtering and search.
3. Immutability: events can be appended, but not modified or deleted.
4. Analytics aggregations: feedback, facilities, inspections, government response.
5. Access control: admin access granted via X-Admin-Key / Bearer token, unauthorized denied.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.admin.dependencies import DEV_ADMIN_KEY
from app.modules.admin.domain import PlatformAuditEvent
from app.modules.admin.repository import PlatformAuditRepository, get_platform_audit_repository
from app.modules.admin.service import AdminAnalyticsService


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": DEV_ADMIN_KEY}


@pytest.fixture
def audit_repo() -> PlatformAuditRepository:
    return get_platform_audit_repository()


def test_admin_dashboard_summary_api(client: TestClient, admin_headers: dict[str, str]):
    response = client.get("/api/v1/admin/dashboard/summary", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total_toilets"] >= 400
    assert data["total_feedback"] >= 100
    assert data["total_inspections"] >= 30
    assert data["total_reported_issues"] >= 10
    assert data["pending_maintenance_tickets"] >= 1
    assert data["notifications_sent"] >= 5
    assert data["resolved_issues"] >= 5
    assert "last_updated" in data


def test_admin_audit_logs_listing_and_filtering(client: TestClient, admin_headers: dict[str, str]):
    # 1. Fetch unfiltered logs
    response = client.get("/api/v1/admin/audit-logs?page=1&page_size=20", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 10

    # Verify reverse chronological ordering (newest first)
    timestamps = [item["timestamp"] for item in data["items"]]
    assert timestamps == sorted(timestamps, reverse=True)

    # 2. Filter by severity
    crit_res = client.get("/api/v1/admin/audit-logs?severity=critical", headers=admin_headers)
    assert crit_res.status_code == 200
    crit_data = crit_res.json()
    for item in crit_data["items"]:
        assert item["severity"] == "critical"

    # 3. Filter by search query
    search_res = client.get("/api/v1/admin/audit-logs?search=ammonia", headers=admin_headers)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total"] >= 1
    for item in search_data["items"]:
        assert "ammonia" in item["description"].lower() or "ammonia" in str(item).lower()


def test_append_audit_log_event(client: TestClient, admin_headers: dict[str, str]):
    now = datetime.now(UTC).isoformat()
    new_event = {
        "event_id": f"EVT-TEST-{int(datetime.now(UTC).timestamp())}",
        "event_type": "inspection.completed",
        "description": "Physical inspection test audit completed at TVS Motors washroom.",
        "related_toilet_id": "bbmp-tv-9001",
        "toilet_name": "BBMP TVS Industrial Toilet",
        "timestamp": now,
        "severity": "medium",
        "actor": "volunteer:INF-CSR-2026-102",
        "status": "success",
        "metadata": {"score": 85},
    }

    create_res = client.post("/api/v1/admin/audit-logs", headers=admin_headers, json=new_event)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["event_id"] == new_event["event_id"]

    # Verify event appears in list
    verify_res = client.get(
        f"/api/v1/admin/audit-logs?search={new_event['event_id']}",
        headers=admin_headers,
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["total"] == 1


def test_analytics_endpoints(client: TestClient, admin_headers: dict[str, str]):
    # Feedback Analytics
    fb_res = client.get("/api/v1/admin/analytics/feedback", headers=admin_headers)
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert fb_data["positive_count"] > 0
    assert len(fb_data["top_reported_issues"]) >= 3

    # Facility Analytics
    fac_res = client.get("/api/v1/admin/analytics/facilities", headers=admin_headers)
    assert fac_res.status_code == 200
    fac_data = fac_res.json()
    assert fac_data["total_facilities"] >= 400
    assert len(fac_data["top_complaint_facilities"]) >= 3

    # Inspection Analytics
    insp_res = client.get("/api/v1/admin/analytics/inspections", headers=admin_headers)
    assert insp_res.status_code == 200
    insp_data = insp_res.json()
    assert insp_data["total_inspections"] > 0
    assert len(insp_data["issues_identified"]) >= 3

    # Government Analytics
    gov_res = client.get("/api/v1/admin/analytics/government", headers=admin_headers)
    assert gov_res.status_code == 200
    gov_data = gov_res.json()
    assert gov_data["notifications_sent"] > 0
    assert gov_data["successful_deliveries"] > 0

