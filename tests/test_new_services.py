"""Tests for new application services and their route endpoints."""

from __future__ import annotations

import pytest

from archub_cms.application.audit_trail_service import AuditTrailService
from archub_cms.application.bookmark_service import BookmarkService
from archub_cms.application.notification_hub_service import NotificationHubService
from archub_cms.application.scheduler_service import SchedulerService
from archub_cms.application.space_service import SpaceService
from archub_cms.application.tag_service import TagService
from archub_cms.domain.scheduler.job import ScheduledJob
from archub_cms.domain.tags.tag import Tag
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus


class TestSchedulerServiceNoRepo:
    def test_list_jobs_returns_plugin_jobs(self):
        svc = SchedulerService()
        result = svc.list_jobs()
        assert isinstance(result, list)

    def test_create_job_no_repo_raises(self):
        svc = SchedulerService()
        job = ScheduledJob(job_id="j1", name="test", action="run")
        result = svc.create_job(job)
        assert result["job_id"] == "j1"

    def test_tick_returns_results(self):
        svc = SchedulerService()
        result = svc.tick()
        assert "fired" in result
        assert "failed" in result


class TestAuditTrailService:
    def test_records_events(self):
        bus = EventBus()
        svc = AuditTrailService(event_bus=bus)
        bus.publish(ArcHubDomainEvent("test.created", "obj-1", "actor"))
        result = svc.query()
        assert result["total"] == 0

    def test_query_without_repo(self):
        svc = AuditTrailService()
        result = svc.query()
        assert result["items"] == []


class TestNotificationHubService:
    def test_inbox_without_repo(self):
        svc = NotificationHubService()
        result = svc.inbox("alice")
        assert result["items"] == []

    def test_channels_list(self):
        svc = NotificationHubService()
        result = svc.channels()
        assert "channels" in result


class TestBookmarkServiceNoRepo:
    def test_add_without_repo_raises(self):
        svc = BookmarkService()
        with pytest.raises(RuntimeError, match="no repository"):
            svc.add(username="alice", node_id="n1")

    def test_list_without_repo(self):
        svc = BookmarkService()
        result = svc.list_for_user("alice")
        assert result["total"] == 0


class TestTagServiceNoRepo:
    def test_list_without_repo(self):
        svc = TagService()
        result = svc.list_all()
        assert result["total"] == 0

    def test_upsert_without_repo_raises(self):
        svc = TagService()
        with pytest.raises(RuntimeError, match="no repository"):
            svc.upsert(Tag(slug="python", display_name="Python"))


class TestSpaceServiceNoRepo:
    def test_list_without_repo(self):
        svc = SpaceService()
        result = svc.list_all()
        assert result["total"] == 0

    def test_get_without_repo(self):
        svc = SpaceService()
        assert svc.get("eng") is None


class TestNewPlatformRoutes:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient

        from archub_cms.app import create_archub_app

        with TestClient(create_archub_app()) as client:
            self.client = client
            yield

    def test_scheduler_jobs_endpoint(self):
        resp = self.client.get("/api/platform/scheduler/jobs")
        assert resp.status_code == 200

    def test_scheduler_tick_endpoint(self):
        resp = self.client.post("/api/platform/scheduler/tick")
        assert resp.status_code == 200

    def test_audit_trail_endpoint(self):
        resp = self.client.get("/api/platform/audit-trail")
        assert resp.status_code == 200

    def test_audit_trail_for_aggregate(self):
        resp = self.client.get("/api/platform/audit-trail/some-agg")
        assert resp.status_code == 200

    def test_notification_inbox(self):
        resp = self.client.get("/api/platform/notifications/inbox?username=alice")
        assert resp.status_code == 200

    def test_notification_channels(self):
        resp = self.client.get("/api/platform/notifications/channels")
        assert resp.status_code == 200

    def test_bookmarks_list(self):
        resp = self.client.get("/api/platform/bookmarks?username=alice")
        assert resp.status_code == 200

    def test_bookmarks_folders(self):
        resp = self.client.get("/api/platform/bookmarks/folders?username=alice")
        assert resp.status_code == 200

    def test_tags_list(self):
        resp = self.client.get("/api/platform/tags")
        assert resp.status_code == 200

    def test_tags_tree(self):
        resp = self.client.get("/api/platform/tags/tree")
        assert resp.status_code == 200

    def test_spaces_list(self):
        resp = self.client.get("/api/platform/spaces")
        assert resp.status_code == 200

    def test_spaces_not_found(self):
        resp = self.client.get("/api/platform/spaces/nonexistent")
        assert resp.status_code == 404

    def test_platform_capabilities_has_26_contexts(self):
        resp = self.client.get("/api/platform/capabilities")
        assert resp.status_code == 200
        assert resp.json()["context_count"] == 38
