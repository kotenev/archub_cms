"""Tests for new kernel modules: Outbox, SnapshotStore, DomainRegistry, HealthCheck, RetryPolicy, AsyncCommandBus."""

from __future__ import annotations

import sqlite3

import pytest

from archub_cms.kernel.async_command_bus import AsyncCommandBus
from archub_cms.kernel.domain_registry import DomainRegistry, get_domain_registry
from archub_cms.kernel.health_check import (
    HealthCheckResult,
    HealthCheckService,
    get_health_check_service,
)
from archub_cms.kernel.outbox import SqliteOutboxStore
from archub_cms.kernel.retry_policy import RetryPolicy
from archub_cms.kernel.snapshot_store import SqliteSnapshotStore


class TestOutboxStore:
    def test_append_and_pending(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteOutboxStore(conn)
        entry_id = store.append("agg-1", "test.event", {"key": "val"})
        assert entry_id > 0
        pending = store.pending()
        assert len(pending) == 1
        assert pending[0].aggregate_id == "agg-1"
        assert pending[0].event_type == "test.event"

    def test_mark_dispatched(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteOutboxStore(conn)
        id1 = store.append("a1", "e1", {})
        id2 = store.append("a2", "e2", {})
        store.mark_dispatched((id1,))
        pending = store.pending()
        assert len(pending) == 1
        assert pending[0].entry_id == id2


class TestSnapshotStore:
    def test_save_and_load(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteSnapshotStore(conn)
        state = {"title": "Test", "version": 5}
        store.save("agg-1", "Content", state, 5)
        loaded = store.load_latest("agg-1")
        assert loaded is not None
        assert loaded["title"] == "Test"
        assert loaded["_snapshot_version"] == 5

    def test_load_nonexistent(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteSnapshotStore(conn)
        assert store.load_latest("nonexistent") is None


class TestDomainRegistry:
    def test_register_and_get(self):
        registry = DomainRegistry()
        registry.register("content", "repository", object())
        svc = registry.get("content", "repository")
        assert svc is not None

    def test_require_missing(self):
        registry = DomainRegistry()
        with pytest.raises(LookupError):
            registry.require("missing", "service")

    def test_context_names(self):
        registry = DomainRegistry()
        registry.register("content", "repo", object())
        registry.register("media", "repo", object())
        assert "content" in registry.context_names()
        assert "media" in registry.context_names()


class TestHealthCheck:
    def test_register_and_check(self):
        svc = HealthCheckService()
        svc.register("db", lambda: HealthCheckResult("db", True, "ok"))
        svc.register("cache", lambda: HealthCheckResult("cache", True, "connected"))
        result = svc.check()
        assert result["status"] == "healthy"
        assert result["healthy_count"] == 2

    def test_degraded_status(self):
        svc = HealthCheckService()
        svc.register("db", lambda: HealthCheckResult("db", True))
        svc.register("external", lambda: HealthCheckResult("external", False, "timeout"))
        result = svc.check()
        assert result["status"] == "degraded"
        assert result["healthy_count"] == 1


class TestRetryPolicy:
    def test_success_on_first_try(self):
        policy = RetryPolicy(max_retries=3)
        result = policy.execute(lambda: "ok")
        assert result.success
        assert result.attempts == 1

    def test_retry_on_failure(self):
        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        calls = [0]

        def failing():
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("fail")
            return "ok"

        result = policy.execute(failing)
        assert result.success
        assert result.attempts == 3

    def test_max_retries_exceeded(self):
        policy = RetryPolicy(max_retries=2, base_delay=0.01)

        def always_fail():
            raise ValueError("always fails")

        result = policy.execute(always_fail)
        assert not result.success
        assert "always fails" in result.last_error


class TestAsyncCommandBus:
    def test_enqueue_and_stats(self):
        bus = AsyncCommandBus()
        cmd_id = bus.enqueue("test.command", {"key": "val"})
        assert cmd_id.startswith("cmd-")
        assert bus.pending_count == 1

    def test_process_one_no_handler(self):
        bus = AsyncCommandBus()
        bus.enqueue("unknown.command", {})
        result = bus.process_one()
        assert result is not None
        assert result["status"] == "no_handler"

    def test_process_with_handler(self):
        bus = AsyncCommandBus()
        bus.register_handler("test.cmd", lambda p: p.get("result", "done"))
        bus.enqueue("test.cmd", {"result": "success"})
        result = bus.process_one()
        assert result["status"] == "completed"
        assert result["result"] == "success"
        assert bus.completed_count == 1


class TestGetSingletons:
    def test_get_domain_registry(self):
        r1 = get_domain_registry()
        r2 = get_domain_registry()
        assert r1 is r2

    def test_get_health_check_service(self):
        h1 = get_health_check_service()
        h2 = get_health_check_service()
        assert h1 is h2
