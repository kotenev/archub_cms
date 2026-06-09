"""Tests for new kernel modules: Mediator, AggregateRoot, ValueObjects, Saga, EventStore, ProjectionStore."""

from __future__ import annotations

import sqlite3

import pytest

from archub_cms.kernel.aggregate_root import AggregateRoot
from archub_cms.kernel.event_store import SqliteEventStore
from archub_cms.kernel.events import ArcHubDomainEvent
from archub_cms.kernel.mediator import Mediator, get_mediator
from archub_cms.kernel.projection_store import SqliteProjectionStore
from archub_cms.kernel.saga import (
    Saga,
    SagaContext,
    SagaDefinition,
    SagaStatus,
    SagaStep,
    SimpleSagaRunner,
)
from archub_cms.kernel.value_objects import Identity, Page, Pagination, Timestamp


class _SampleAggregate(AggregateRoot):
    def __init__(self, aggregate_id: str, name: str = "", version: int = 0) -> None:
        super().__init__(aggregate_id, version=version)
        self.name = name

    @classmethod
    def reconstitute(cls, aggregate_id: str, state: dict) -> _SampleAggregate:
        return cls(aggregate_id, name=state.get("name", ""), version=state.get("version", 0))


class TestAggregateRoot:
    def test_equality_by_id(self):
        a = _SampleAggregate("1", name="x")
        b = _SampleAggregate("1", name="y")
        assert a == b

    def test_inequality_by_type(self):
        a = _SampleAggregate("1")

        class Other(AggregateRoot):
            @classmethod
            def reconstitute(cls, aggregate_id, state) -> Other:
                return object.__new__(cls)  # type: ignore[return-value]

        c = AggregateRoot.__new__(Other)  # type: ignore[call-arg]
        c.aggregate_id = "1"
        c.version = 0
        c._pending_events = []
        assert a != c

    def test_event_collection(self):
        agg = _SampleAggregate("1")
        event = ArcHubDomainEvent("test.created", "1", "actor")
        agg._record_event(event)
        assert agg.has_pending_events
        events = agg.collect_events()
        assert len(events) == 1
        assert not agg.has_pending_events
        assert agg.version == 1

    def test_hash(self):
        a = _SampleAggregate("1")
        assert hash(a) == hash(_SampleAggregate("1"))


class TestMediator:
    def test_send_command(self):
        mediator = Mediator()
        mediator.register_command(str, lambda c: f"handled:{c}")

        class MyCommand:
            pass

        mediator.register_command(MyCommand, lambda c: "cmd-result")
        result = mediator.send(MyCommand())
        assert result == "cmd-result"

    def test_query(self):
        mediator = Mediator()

        class MyQuery:
            pass

        mediator.register_query(MyQuery, lambda q: 42)
        assert mediator.query(MyQuery()) == 42

    def test_unregistered_command_raises(self):
        mediator = Mediator()

        class Unknown:
            pass

        with pytest.raises(LookupError):
            mediator.send(Unknown())

    def test_middleware(self):
        mediator = Mediator()
        log: list[str] = []
        mediator.register_command(str, lambda c: "ok")
        mediator.add_middleware(lambda msg, next_fn: (log.append("before"), next_fn())[1])
        mediator.send("hello")
        assert log == ["before"]

    def test_handler_count(self):
        mediator = Mediator()
        mediator.register_command(str, lambda c: c)
        mediator.register_query(int, lambda q: q)
        counts = mediator.handler_count()
        assert counts["commands"] == 1
        assert counts["queries"] == 1


class TestValueObjects:
    def test_identity(self):
        a = Identity("node-1")
        assert a == "node-1"
        assert a == Identity("node-1")
        assert hash(a) == hash(Identity("node-1"))
        assert "node-1" in {a}

    def test_identity_generate(self):
        id1 = Identity.generate("test-")
        assert id1.value.startswith("test-")
        assert id1 != Identity.generate("test-")

    def test_timestamp(self):
        t = Timestamp.now()
        assert t.epoch > 0
        assert not t.is_zero
        assert Timestamp.from_epoch(0.0).is_zero

    def test_pagination(self):
        p = Pagination(offset=10, limit=20)
        assert p.next_page().offset == 30
        with pytest.raises(ValueError):
            Pagination(limit=0)

    def test_page(self):
        p = Page(items=(1, 2, 3), total=10, pagination=Pagination(offset=0, limit=3))
        assert p.has_next
        assert p.page_number == 1
        assert p.total_pages == 4


class TestEventStore:
    def test_append_and_load(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteEventStore(conn)
        event = ArcHubDomainEvent("node.created", "node-1", "editor", {"key": "val"})
        store.append(event)
        loaded = store.load("node-1")
        assert len(loaded) == 1
        assert loaded[0].event_type == "node.created"
        assert loaded[0].metadata == {"key": "val"}

    def test_load_all_after(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteEventStore(conn)
        for i in range(5):
            store.append(ArcHubDomainEvent(f"evt.{i}", "agg", "actor"))
        recent = store.load_all_after(3)
        assert len(recent) == 2

    def test_global_sequence(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteEventStore(conn)
        assert store.global_sequence() == 0
        store.append(ArcHubDomainEvent("e", "a", "u"))
        assert store.global_sequence() == 1


class TestProjectionStore:
    def test_save_and_load(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteProjectionStore(conn)
        store.save("recent_docs", "/cms/doc1", {"title": "Doc 1"})
        result = store.load("recent_docs", "/cms/doc1")
        assert result is not None
        assert result["title"] == "Doc 1"

    def test_load_all(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteProjectionStore(conn)
        store.save("ctx", "k1", {"v": 1})
        store.save("ctx", "k2", {"v": 2})
        all_items = store.load_all("ctx")
        assert len(all_items) == 2

    def test_position_tracking(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        store = SqliteProjectionStore(conn)
        assert store.get_position("my_proj") == 0
        store.mark_position("my_proj", 42)
        assert store.get_position("my_proj") == 42


class TestSaga:
    def test_saga_context_advance(self):
        ctx = SagaContext(saga_id="s1", saga_type="publish")
        assert ctx.status == SagaStatus.PENDING
        running = ctx.advance()
        assert running.status == SagaStatus.RUNNING
        assert running.current_step == 1

    def test_saga_context_fail(self):
        ctx = SagaContext(saga_id="s1", saga_type="test")
        failed = ctx.fail("boom")
        assert failed.status == SagaStatus.FAILED
        assert "boom" in failed.errors

    def test_saga_runner_registers_and_tracks(self):
        bus = __import__("archub_cms.kernel.events", fromlist=["EventBus"]).EventBus()

        class TestSaga(Saga):
            def definition(self) -> SagaDefinition:
                return SagaDefinition(
                    saga_type="test",
                    trigger_event="content.published",
                    steps=(SagaStep(name="step1", reacts_to="step1.done"),),
                )

            def initial_context(self, saga_id: str) -> SagaContext:
                return SagaContext(saga_id=saga_id, saga_type="test", status=SagaStatus.PENDING)

        runner = SimpleSagaRunner(event_bus=bus)
        runner.register(TestSaga())
        bus.publish(ArcHubDomainEvent("content.published", "node-1", "editor"))
        assert len(runner.active_sagas()) == 1

    def test_get_mediator_singleton(self):
        m1 = get_mediator()
        m2 = get_mediator()
        assert m1 is m2
