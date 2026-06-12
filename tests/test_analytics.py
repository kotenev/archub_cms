"""Tests for the analytics / health bounded context (Phase 15)."""

from __future__ import annotations

import pytest

from archub_cms.application.analytics_service import get_archub_analytics_service
from archub_cms.demo import seed_demo_content
from archub_cms.domain.analytics.models import ActivityEntry, AuditIssue, HealthReport
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture
def cms(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    service = get_archub_cms_service()
    seed_demo_content(service)
    return service


# --- domain: score / grade -----------------------------------------------


def test_health_score_and_grade():
    assert HealthReport(ok=True).grade() == "A"
    assert HealthReport(ok=True).score() == 100
    assert HealthReport(ok=True, warning_count=3).score() == 91  # 100 - 9
    assert HealthReport(ok=True, warning_count=3).grade() == "A"
    bad = HealthReport(ok=False, error_count=4, warning_count=2)
    assert bad.score() == 46  # 100 - 48 - 6
    assert bad.grade() == "F"
    assert HealthReport(ok=False, error_count=1).grade() == "B"  # score 88


def test_health_from_result_maps_issues():
    issue = AuditIssue(severity="error", message="boom", node_id="n", route_path="/cms/x")
    report = HealthReport.from_result(
        {"ok": False, "nodes": 5, "error_count": 1, "issues": [issue]}
    )
    assert report.issue_count == 1
    assert report.issues[0].message == "boom"
    assert report.as_dict()["grade"] == "B"


def test_from_result_accepts_object_issues():
    class _Obj:
        severity = "warning"
        message = "w"
        node_id = "n"
        route_path = "/cms/y"
        content_type_alias = "page"

    report = HealthReport.from_result({"ok": True, "warning_count": 1, "issues": [_Obj()]})
    assert report.issues[0].severity == "warning"


def test_activity_entry_model():
    e = ActivityEntry(action="content.created", actor="ed", node_id="n")
    assert e.as_dict()["action"] == "content.created"


# --- application service over real content --------------------------------


def test_health_and_dashboard(cms):
    svc = get_archub_analytics_service(cms=cms)
    health = svc.health()
    assert health["ok"] is True
    assert 0 <= health["score"] <= 100
    assert health["grade"] in {"A", "B", "C", "D", "F"}
    assert health["nodes"] >= 1

    dashboard = svc.dashboard()
    assert "health" in dashboard and "stats" in dashboard
    assert "recent_activity" in dashboard


def test_activity_feed_and_stats(cms):
    svc = get_archub_analytics_service(cms=cms)
    activity = svc.activity(limit=50)
    assert activity["total"] >= 1
    assert "content.published" in activity["by_action"]

    stats = svc.stats()
    assert isinstance(stats, dict) and stats.get("nodes", 0) >= 1


# --- endpoints ------------------------------------------------------------


def test_analytics_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        health = client.get("/api/platform/analytics/health")
        assert health.status_code == 200
        assert "score" in health.json() and "grade" in health.json()

        dashboard = client.get("/api/platform/analytics/dashboard")
        assert dashboard.status_code == 200 and "health" in dashboard.json()

        stats = client.get("/api/platform/analytics/stats")
        assert stats.status_code == 200 and stats.json().get("nodes", 0) >= 1

        activity = client.get("/api/platform/analytics/activity", params={"limit": 10})
        assert activity.status_code == 200 and "by_action" in activity.json()
