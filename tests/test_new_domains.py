"""Tests for new domain contexts: scheduler, audit_trail, notifications, tags, bookmarks, spaces."""

from __future__ import annotations

from archub_cms.domain.audit_trail.entry import AuditEntry, AuditQuery
from archub_cms.domain.bookmarks.bookmark import Bookmark, BookmarkFolder
from archub_cms.domain.content.diff_service import DiffType, compute_content_diff
from archub_cms.domain.notifications.notification import Notification, NotificationPreference
from archub_cms.domain.scheduler.job import JobStatus, ScheduledJob
from archub_cms.domain.spaces.space import Space, SpaceSettings
from archub_cms.domain.specifications import ActiveJobSpec, PublicSpaceSpec, TaggedWithSpec
from archub_cms.domain.tags.tag import Tag, TagNode


class TestScheduledJob:
    def test_validate_ok(self):
        job = ScheduledJob(job_id="j1", name="test", action="health")
        result = job.validate()
        assert result.ok

    def test_validate_missing_action(self):
        job = ScheduledJob(job_id="j1", name="test", action="")
        result = job.validate()
        assert not result.ok

    def test_pause_resume(self):
        job = ScheduledJob(job_id="j1", name="test", action="run")
        assert job.status == JobStatus.ACTIVE
        job.pause()
        assert job.status == JobStatus.PAUSED
        job.resume()
        assert job.status == JobStatus.ACTIVE

    def test_can_fire(self):
        job = ScheduledJob(job_id="j1", name="test", action="run", next_run_at=100.0)
        assert job.can_fire(200.0)
        assert not job.can_fire(50.0)

    def test_mark_fired_completes_one_shot(self):
        job = ScheduledJob(job_id="j1", name="test", action="run", next_run_at=100.0)
        job.mark_fired("ok", now=100.0)
        assert job.run_count == 1
        assert job.status == JobStatus.COMPLETED

    def test_cron_stays_active(self):
        job = ScheduledJob(
            job_id="j1",
            name="test",
            action="run",
            cron_expression="*/5 * * * *",
            next_run_at=100.0,
        )
        job.mark_fired("ok", now=100.0)
        assert job.status == JobStatus.ACTIVE


class TestAuditEntry:
    def test_as_dict(self):
        entry = AuditEntry(
            entry_id="e1",
            action="created",
            aggregate_id="n1",
            aggregate_type="content",
            actor="admin",
            timestamp=100.0,
        )
        d = entry.as_dict()
        assert d["action"] == "created"
        assert d["actor"] == "admin"

    def test_query_matches(self):
        entry = AuditEntry(
            entry_id="e1",
            action="created",
            aggregate_id="n1",
            aggregate_type="content",
            actor="admin",
            timestamp=100.0,
        )
        q = AuditQuery(actor="admin")
        assert q.matches(entry)
        q2 = AuditQuery(actor="other")
        assert not q2.matches(entry)

    def test_query_time_range(self):
        entry = AuditEntry(
            entry_id="e1",
            action="x",
            aggregate_id="a",
            aggregate_type="",
            actor="",
            timestamp=50.0,
        )
        assert AuditQuery(from_timestamp=10.0, to_timestamp=100.0).matches(entry)
        assert not AuditQuery(from_timestamp=60.0).matches(entry)
        assert not AuditQuery(to_timestamp=40.0).matches(entry)


class TestNotification:
    def test_mark_read(self):
        n = Notification(notification_id="n1", recipient="alice", title="Test", body="Hi")
        assert not n.read
        n.mark_read()
        assert n.read

    def test_preference(self):
        pref = NotificationPreference(
            username="alice", event_type="comment", channels=("in_app", "email")
        )
        d = pref.as_dict()
        assert d["channels"] == ["in_app", "email"]


class TestTag:
    def test_tag_as_dict(self):
        tag = Tag(slug="python", display_name="Python", aliases=("py",))
        d = tag.as_dict()
        assert d["slug"] == "python"
        assert d["aliases"] == ["py"]

    def test_tag_node_flatten(self):
        child = Tag(slug="child", display_name="Child")
        root = Tag(slug="root", display_name="Root")
        node = TagNode(tag=root, children=(TagNode(tag=child),))
        flat = node.flatten()
        assert len(flat) == 2
        assert flat[0].slug == "root"
        assert flat[1].slug == "child"


class TestBookmark:
    def test_bookmark_as_dict(self):
        b = Bookmark(bookmark_id="b1", username="alice", node_id="n1", created_at=100.0)
        d = b.as_dict()
        assert d["username"] == "alice"

    def test_folder(self):
        f = BookmarkFolder(folder_id="f1", username="alice", name="Docs")
        assert f.as_dict()["name"] == "Docs"


class TestSpace:
    def test_space_as_dict(self):
        space = Space(space_key="eng", name="Engineering", owner="alice")
        d = space.as_dict()
        assert d["space_key"] == "eng"
        assert d["settings"]["theme"] == "default"

    def test_space_settings(self):
        s = SpaceSettings(icon="code", color="#000000")
        d = s.as_dict()
        assert d["icon"] == "code"


class TestSpecifications:
    def test_active_job_spec(self):
        job = ScheduledJob(job_id="j1", name="t", action="run")
        assert ActiveJobSpec().is_satisfied_by(job)
        job.pause()
        assert not ActiveJobSpec().is_satisfied_by(job)

    def test_public_space_spec(self):
        space = Space(space_key="pub", name="Public", visibility="public")
        assert PublicSpaceSpec().is_satisfied_by(space)
        private = Space(space_key="priv", name="Private", visibility="private")
        assert not PublicSpaceSpec().is_satisfied_by(private)

    def test_tagged_with_spec(self):
        tagged = type("Obj", (), {"tags": ("python", "web")})()
        assert TaggedWithSpec("python").is_satisfied_by(tagged)
        assert not TaggedWithSpec("java").is_satisfied_by(tagged)


class TestContentDiff:
    def test_added_field(self):
        diffs = compute_content_diff({}, {"title": "New"})
        assert len(diffs) == 1
        assert diffs[0].diff_type == DiffType.ADDED

    def test_removed_field(self):
        diffs = compute_content_diff({"title": "Old"}, {})
        assert len(diffs) == 1
        assert diffs[0].diff_type == DiffType.REMOVED

    def test_changed_field(self):
        diffs = compute_content_diff({"title": "Old"}, {"title": "New"})
        assert len(diffs) == 1
        assert diffs[0].diff_type == DiffType.CHANGED
        assert diffs[0].old_value == "Old"
        assert diffs[0].new_value == "New"

    def test_no_changes(self):
        assert compute_content_diff({"a": 1}, {"a": 1}) == []
