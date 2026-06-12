"""Tests for all 12 new domain bounded contexts."""

from __future__ import annotations

from archub_cms.domain.activity_feed.models import ActivityEntry, ActivityType
from archub_cms.domain.ai_chat.models import ChatMessage, ChatRole, Conversation
from archub_cms.domain.comments_thread.models import Comment, CommentStatus, CommentThread
from archub_cms.domain.custom_fields.models import (
    CustomField,
    CustomFieldDefinition,
    CustomFieldType,
)
from archub_cms.domain.dashboard.models import DashboardLayout, DashboardWidget, WidgetType
from archub_cms.domain.embedding_store.models import EmbeddingEntry, EmbeddingStatus
from archub_cms.domain.live_edit.models import (
    EditOperation,
    EditSession,
    OperationType,
    UserPresence,
)
from archub_cms.domain.page_cloning.models import CloneOptions, CloneResult
from archub_cms.domain.pdf_export.models import ExportFormat, ExportJob, ExportStatus
from archub_cms.domain.permissions.models import Permission, PermissionLevel
from archub_cms.domain.revisions_diff.models import (
    DiffBlock,
    DiffLine,
    DiffType,
    RevisionComparison,
)
from archub_cms.domain.templates.models import PageTemplate, TemplateCategory


class TestCommentsThread:
    def test_comment_as_dict(self):
        c = Comment(comment_id="c1", thread_id="t1", author="alice", body="Hi")
        d = c.as_dict()
        assert d["comment_id"] == "c1"
        assert d["author"] == "alice"

    def test_comment_resolve(self):
        c = Comment(comment_id="c1", thread_id="t1", author="alice", body="Hi")
        c.resolve()
        assert c.status == CommentStatus.RESOLVED

    def test_comment_reactions(self):
        c = Comment(comment_id="c1", thread_id="t1", author="alice", body="Hi")
        c.add_reaction("👍", "bob")
        c.add_reaction("👍", "carol")
        assert len(c.reactions["👍"]) == 2
        c.remove_reaction("👍", "bob")
        assert len(c.reactions["👍"]) == 1

    def test_thread_as_dict(self):
        t = CommentThread(thread_id="t1", node_id="n1", title="Discussion")
        d = t.as_dict()
        assert d["thread_id"] == "t1"
        assert d["node_id"] == "n1"


class TestTemplates:
    def test_page_template_as_dict(self):
        t = PageTemplate(template_id="t1", name="Meeting Notes", body="# Title")
        d = t.as_dict()
        assert d["template_id"] == "t1"
        assert d["category"] == TemplateCategory.BLANK

    def test_template_categories_exist(self):
        assert TemplateCategory.MEETING_NOTES == "meeting_notes"
        assert TemplateCategory.KB_ARTICLE == "kb_article"


class TestPermissions:
    def test_permission_as_dict(self):
        p = Permission(
            permission_id="p1",
            subject_type="user",
            subject_id="alice",
            resource_type="page",
            resource_id="/docs/page",
            level=PermissionLevel.EDIT,
        )
        d = p.as_dict()
        assert d["level"] == PermissionLevel.EDIT

    def test_permission_implies(self):
        view = Permission(
            permission_id="p1",
            subject_type="user",
            subject_id="alice",
            resource_type="page",
            resource_id="x",
            level=PermissionLevel.VIEW,
        )
        edit = Permission(
            permission_id="p2",
            subject_type="user",
            subject_id="alice",
            resource_type="page",
            resource_id="x",
            level=PermissionLevel.EDIT,
        )
        admin = Permission(
            permission_id="p3",
            subject_type="user",
            subject_id="alice",
            resource_type="page",
            resource_id="x",
            level=PermissionLevel.ADMIN,
        )
        assert view.implies(PermissionLevel.VIEW)
        assert not view.implies(PermissionLevel.EDIT)
        assert edit.implies(PermissionLevel.VIEW)
        assert admin.implies(PermissionLevel.EDIT)


class TestAIChat:
    def test_chat_message_as_dict(self):
        m = ChatMessage(message_id="m1", conversation_id="c1", role=ChatRole.USER, content="Hello")
        d = m.as_dict()
        assert d["role"] == ChatRole.USER

    def test_conversation_as_dict(self):
        c = Conversation(conversation_id="c1", title="Chat", owner="alice")
        d = c.as_dict()
        assert d["owner"] == "alice"
        assert not d["is_archived"]

    def test_conversation_archive(self):
        c = Conversation(conversation_id="c1", title="Chat", owner="alice")
        c.archive()
        assert c.is_archived


class TestDashboard:
    def test_dashboard_widget_as_dict(self):
        w = DashboardWidget(widget_id="w1", widget_type=WidgetType.RECENT_PAGES, title="Recent")
        d = w.as_dict()
        assert d["widget_type"] == WidgetType.RECENT_PAGES

    def test_dashboard_layout_as_dict(self):
        w = DashboardWidget(widget_id="w1", widget_type=WidgetType.BOOKMARKS, title="Favs")
        layout = DashboardLayout(layout_id="l1", owner="alice", widgets=(w,))
        d = layout.as_dict()
        assert len(d["widgets"]) == 1


class TestActivityFeed:
    def test_activity_entry_as_dict(self):
        a = ActivityEntry(
            entry_id="a1",
            activity_type=ActivityType.PAGE_CREATED,
            actor="alice",
            target_type="page",
            target_id="/docs/new",
        )
        d = a.as_dict()
        assert d["activity_type"] == ActivityType.PAGE_CREATED


class TestCustomFields:
    def test_custom_field_definition_as_dict(self):
        d = CustomFieldDefinition(
            field_id="f1",
            name="Priority",
            field_type=CustomFieldType.SELECT,
            options=("High", "Medium", "Low"),
        )
        result = d.as_dict()
        assert result["field_type"] == CustomFieldType.SELECT
        assert len(result["options"]) == 3

    def test_custom_field_as_dict(self):
        defn = CustomFieldDefinition(field_id="f1", name="Status", field_type=CustomFieldType.TEXT)
        f = CustomField(field_id="f1", definition=defn, node_id="n1", value="Draft")
        result = f.as_dict()
        assert result["value"] == "Draft"


class TestPageCloning:
    def test_clone_options_as_dict(self):
        o = CloneOptions(source_id="src1", owner="alice")
        d = o.as_dict()
        assert d["source_id"] == "src1"
        assert d["clone_children"] is True

    def test_clone_result_as_dict(self):
        r = CloneResult(
            source_id="s1",
            cloned_root_id="c1",
            pages_cloned=5,
            attachments_cloned=2,
            custom_fields_cloned=1,
        )
        d = r.as_dict()
        assert d["pages_cloned"] == 5


class TestPDFExport:
    def test_export_job_status_transitions(self):
        job = ExportJob(
            job_id="j1",
            format=ExportFormat.PDF,
            target_type="page",
            target_id="p1",
            requester="alice",
        )
        assert job.status == ExportStatus.PENDING
        job.mark_processing()
        assert job.status == ExportStatus.PROCESSING
        job.mark_completed("/exports/j1.pdf")
        assert job.status == ExportStatus.COMPLETED
        assert job.output_path == "/exports/j1.pdf"

    def test_export_job_failed(self):
        job = ExportJob(
            job_id="j1",
            format=ExportFormat.PDF,
            target_type="page",
            target_id="p1",
            requester="alice",
        )
        job.mark_failed("timeout")
        assert job.status == ExportStatus.FAILED
        assert "timeout" in job.error


class TestEmbeddingStore:
    def test_embedding_entry_as_dict(self):
        e = EmbeddingEntry(
            entry_id="e1", route_path="/docs/page", model="text-embedding-3-small", dim=1536
        )
        d = e.as_dict()
        assert d["dim"] == 1536
        assert d["status"] == EmbeddingStatus.INDEXED


class TestRevisionsDiff:
    def test_diff_line_as_dict(self):
        line = DiffLine(
            line_number_old=1, line_number_new=1, content="Hello", diff_type=DiffType.UNCHANGED
        )
        d = line.as_dict()
        assert d["diff_type"] == DiffType.UNCHANGED

    def test_revision_comparison_as_dict(self):
        block = DiffBlock(start_old=1, start_new=1, lines=())
        comp = RevisionComparison(node_id="n1", old_revision=1, new_revision=2, blocks=(block,))
        d = comp.as_dict()
        assert d["old_revision"] == 1
        assert len(d["blocks"]) == 1


class TestLiveEdit:
    def test_edit_operation_as_dict(self):
        op = EditOperation(
            operation_id="op1",
            session_id="s1",
            user="alice",
            op_type=OperationType.INSERT,
            position=10,
            content="Hi",
        )
        d = op.as_dict()
        assert d["op_type"] == OperationType.INSERT

    def test_user_presence_as_dict(self):
        p = UserPresence(user="alice", node_id="n1", cursor_position=42, color="#e74c3c")
        d = p.as_dict()
        assert d["cursor_position"] == 42

    def test_edit_session_join_leave(self):
        s = EditSession(session_id="s1", node_id="n1")
        p = UserPresence(user="alice", node_id="n1")
        s.join(p)
        assert "alice" in s.active_users
        s.leave("alice")
        assert "alice" not in s.active_users
