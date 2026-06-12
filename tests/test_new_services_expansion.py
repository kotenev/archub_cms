"""Tests for new application services and route endpoints."""

from __future__ import annotations

import pytest

from archub_cms.application.activity_feed_service import (
    ActivityFeedService,
    get_archub_activity_feed_service,
)
from archub_cms.application.ai_chat_service import AIChatService, get_archub_ai_chat_service
from archub_cms.application.comments_thread_service import (
    CommentsThreadService,
    get_archub_comments_thread_service,
)
from archub_cms.application.custom_field_service import (
    get_archub_custom_field_service,
)
from archub_cms.application.dashboard_service import DashboardService, get_archub_dashboard_service
from archub_cms.application.embedding_store_service import (
    EmbeddingStoreService,
    get_archub_embedding_store_service,
)
from archub_cms.application.live_edit_service import LiveEditService, get_archub_live_edit_service
from archub_cms.application.page_cloning_service import (
    PageCloningService,
    get_archub_page_cloning_service,
)
from archub_cms.application.pdf_export_service import (
    PDFExportService,
    get_archub_pdf_export_service,
)
from archub_cms.application.permission_service import (
    PermissionService,
    get_archub_permission_service,
)
from archub_cms.application.revisions_diff_service import (
    get_archub_revisions_diff_service,
)
from archub_cms.application.template_service import TemplateService, get_archub_template_service


class TestCommentsThreadService:
    def test_create_thread(self):
        svc = get_archub_comments_thread_service()
        thread = svc.create_thread("node-1", "Discussion")
        assert thread.thread_id.startswith("thread-")
        assert thread.node_id == "node-1"

    def test_add_comment(self):
        svc = CommentsThreadService()
        comment = svc.add_comment("thread-1", "alice", "Hello world")
        assert comment.comment_id.startswith("comment-")
        assert comment.author == "alice"


class TestTemplateService:
    def test_create_template(self):
        svc = get_archub_template_service()
        tmpl = svc.create_template(
            "Meeting Notes", "# Meeting\n\nAgenda:", "meeting_notes", created_by="alice"
        )
        assert tmpl.template_id.startswith("tmpl-")
        assert tmpl.name == "Meeting Notes"

    def test_list_templates(self):
        svc = TemplateService()
        result = svc.list_templates()
        assert "templates" in result


class TestPermissionService:
    def test_grant_permission(self):
        svc = get_archub_permission_service()
        perm = svc.grant("user", "alice", "page", "/docs/page", "edit", "admin")
        assert perm.permission_id.startswith("perm-")
        assert perm.level == "edit"

    def test_check_access(self):
        svc = PermissionService()
        result = svc.check_access("alice", "page", "/docs/page", "view")
        assert "allowed" in result


class TestAIChatService:
    def test_create_conversation(self):
        svc = get_archub_ai_chat_service()
        conv = svc.create_conversation("New Chat", "alice")
        assert conv.conversation_id.startswith("conv-")
        assert conv.owner == "alice"

    def test_send_message(self):
        svc = AIChatService()
        result = svc.send_message("conv-1", "What is Python?", "alice")
        assert "message" in result


class TestDashboardService:
    def test_create_layout(self):
        svc = get_archub_dashboard_service()
        layout = svc.create_layout("alice", "My Dashboard")
        assert layout.layout_id.startswith("layout-")

    def test_add_widget(self):
        svc = DashboardService()
        widget = svc.add_widget("layout-1", "recent_pages", "Recent", {"limit": 10})
        assert widget.widget_id.startswith("widget-")


class TestActivityFeedService:
    def test_record_activity(self):
        svc = get_archub_activity_feed_service()
        entry = svc.record_activity("page_created", "alice", "page", "/docs/new")
        assert entry.entry_id.startswith("act-")

    def test_list_activities(self):
        svc = ActivityFeedService()
        result = svc.list_activities()
        assert "activities" in result


class TestCustomFieldService:
    def test_define_field(self):
        svc = get_archub_custom_field_service()
        field = svc.define_field("Priority", "select", options=("High", "Medium", "Low"))
        assert field.field_id.startswith("field-")
        assert field.name == "Priority"


class TestPageCloningService:
    def test_clone_page(self):
        from archub_cms.domain.page_cloning.models import CloneOptions

        svc = get_archub_page_cloning_service()
        options = CloneOptions(source_id="src-1", owner="alice")
        result = svc.clone_page(options)
        assert result.source_id == "src-1"

    def test_estimate_clone(self):
        svc = PageCloningService()
        result = svc.estimate_clone("src-1")
        assert "pages" in result


class TestPDFExportService:
    def test_create_export_job(self):
        svc = get_archub_pdf_export_service()
        job = svc.create_export_job("pdf", "page", "/docs/page", "alice")
        assert job.job_id.startswith("export-")

    def test_get_supported_formats(self):
        svc = PDFExportService()
        result = svc.get_supported_formats()
        assert "formats" in result
        assert any(f["id"] == "pdf" for f in result["formats"])


class TestEmbeddingStoreService:
    def test_index_content(self):
        svc = get_archub_embedding_store_service()
        entry = svc.index_content("/docs/page", "text-embedding-3-small", 1536, "hash123")
        assert entry.entry_id.startswith("emb-")

    def test_stats(self):
        svc = EmbeddingStoreService()
        result = svc.stats()
        assert "total_indexed" in result


class TestRevisionsDiffService:
    def test_compare(self):
        svc = get_archub_revisions_diff_service()
        comp = svc.compare("node-1", "old content\nline 2", "new content\nline 2", 1, 2)
        assert comp.node_id == "node-1"
        assert comp.old_revision == 1
        assert comp.new_revision == 2


class TestLiveEditService:
    def test_create_session(self):
        svc = get_archub_live_edit_service()
        session = svc.create_session("node-1")
        assert session.session_id.startswith("session-")
        assert session.node_id == "node-1"

    def test_join_and_leave(self):
        svc = LiveEditService()
        session = svc.create_session("node-1")
        presence = svc.join_session(session.session_id, "alice", "#e74c3c")
        assert presence.user == "alice"
        svc.leave_session(session.session_id, "alice")

    def test_get_active_users(self):
        svc = LiveEditService()
        session = svc.create_session("node-1")
        result = svc.get_active_users(session.session_id)
        assert "users" in result


class TestNewPlatformRoutesEndpoints:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient

        from archub_cms.app import create_archub_app

        with TestClient(create_archub_app()) as client:
            self.client = client
            yield

    def test_comments_threads_endpoint(self):
        resp = self.client.get("/api/platform/comments/threads/node-1")
        assert resp.status_code == 200

    def test_templates_list_endpoint(self):
        resp = self.client.get("/api/platform/templates")
        assert resp.status_code == 200

    def test_permissions_check_endpoint(self):
        resp = self.client.get(
            "/api/platform/permissions/check?user=alice&resource_type=page&resource_id=/x"
        )
        assert resp.status_code == 200

    def test_chat_conversations_endpoint(self):
        resp = self.client.get("/api/platform/chat/conversations?owner=alice")
        assert resp.status_code == 200

    def test_dashboard_endpoint(self):
        resp = self.client.get("/api/platform/dashboard?owner=alice")
        assert resp.status_code == 200

    def test_activity_feed_endpoint(self):
        resp = self.client.get("/api/platform/activity")
        assert resp.status_code == 200

    def test_custom_fields_endpoint(self):
        resp = self.client.get("/api/platform/custom-fields/definitions")
        assert resp.status_code == 200

    def test_export_formats_endpoint(self):
        resp = self.client.get("/api/platform/export/formats")
        assert resp.status_code == 200
        assert "formats" in resp.json()

    def test_embeddings_stats_endpoint(self):
        resp = self.client.get("/api/platform/embeddings/stats")
        assert resp.status_code == 200

    def test_live_edit_session_endpoint(self):
        resp = self.client.post("/api/platform/live-edit/sessions", json={"node_id": "node-1"})
        assert resp.status_code == 200

    def test_health_check_endpoint(self):
        resp = self.client.get("/api/platform/health")
        assert resp.status_code == 200
        assert "status" in resp.json()

    def test_platform_capabilities_38_contexts(self):
        resp = self.client.get("/api/platform/capabilities")
        assert resp.status_code == 200
        assert resp.json()["context_count"] == 38
