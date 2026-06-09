"""Tests for the ITSM Service Desk plugin: workflow engine, BPMN export, requests.

Covers the customizable Jira-style workflow engine, the BPMN 2.0 / Mermaid
serializers, the ITIL request lifecycle with SLA + post-functions, SQLite
persistence, and the plugin loading end-to-end through the PluginHost with all six
extensions wired.
"""

from __future__ import annotations

import importlib.util
import os
from xml.etree import ElementTree as ET

import pytest

from archub_cms.extensibility.example_plugins.itsm.bpmn import to_bpmn_xml, to_mermaid
from archub_cms.extensibility.example_plugins.itsm.repository import (
    PostgresDatabase,
    PostgresRequestRepository,
    SqliteRequestRepository,
)
from archub_cms.extensibility.example_plugins.itsm.request import (
    CloudResource,
    Priority,
    RequestType,
    SlaPolicy,
)
from archub_cms.extensibility.example_plugins.itsm.service_desk import (
    ServiceDesk,
    build_default_schemes,
)
from archub_cms.extensibility.example_plugins.itsm.workflow import (
    StatusCategory,
    WorkflowError,
    WorkflowScheme,
)
from archub_cms.extensibility.host import PluginHost
from archub_cms.infrastructure.db.database import Database
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service

BPMN_NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
}


# -- workflow engine -------------------------------------------------------


def _incident_scheme() -> WorkflowScheme:
    return (
        WorkflowScheme("incident", "Incident")
        .add_status("open", "Open", StatusCategory.TODO, initial=True)
        .add_status("doing", "Doing", StatusCategory.IN_PROGRESS)
        .add_status("done", "Done", StatusCategory.DONE)
        .add_transition("start", "Start", "doing", ["open"])
        .add_transition("finish", "Finish", "done", ["doing"])
        .add_transition("cancel", "Cancel", "done")  # global transition
    )


def test_scheme_builds_and_validates():
    scheme = _incident_scheme()
    assert scheme.is_valid
    assert scheme.initial_status_id == "open"
    assert scheme.validate() == []


def test_available_transitions_respect_origin():
    scheme = _incident_scheme()
    names = {t.id for t in scheme.available_transitions("open")}
    assert "start" in names
    assert "cancel" in names  # global is available from any status
    assert "finish" not in names  # not reachable from open


def test_apply_transition_returns_target():
    scheme = _incident_scheme()
    outcome = scheme.apply("open", "start")
    assert outcome.to_status == "doing"


def test_illegal_transition_rejected():
    scheme = _incident_scheme()
    with pytest.raises(WorkflowError):
        scheme.apply("open", "finish")


def test_conditions_block_transition():
    scheme = (
        WorkflowScheme("c", "Conditioned")
        .add_status("a", "A", StatusCategory.TODO, initial=True)
        .add_status("b", "B", StatusCategory.DONE)
        .add_transition("go", "Go", "b", ["a"], conditions=["is_agent"])
    )
    assert scheme.available_transitions("a") == ()  # no role in context
    assert {t.id for t in scheme.available_transitions("a", context={"actor_role": "agent"})} == {
        "go"
    }
    with pytest.raises(WorkflowError):
        scheme.apply("a", "go", context={"actor_role": "customer"})
    assert scheme.apply("a", "go", context={"actor_role": "agent"}).to_status == "b"


def test_validate_detects_unreachable_and_missing_done():
    scheme = (
        WorkflowScheme("bad", "Bad")
        .add_status("start", "Start", StatusCategory.TODO, initial=True)
        .add_status("island", "Island", StatusCategory.IN_PROGRESS)
    )
    problems = scheme.validate()
    assert any("unreachable" in p for p in problems)
    assert any("no terminal" in p for p in problems)


def test_validate_detects_unknown_target_and_condition():
    scheme = (
        WorkflowScheme("x", "X")
        .add_status("a", "A", StatusCategory.TODO, initial=True)
        .add_status("b", "B", StatusCategory.DONE)
        .add_transition("t", "T", "ghost", ["a"], conditions=["no_such_condition"])
    )
    problems = scheme.validate()
    assert any("unknown status 'ghost'" in p for p in problems)
    assert any("unregistered condition 'no_such_condition'" in p for p in problems)


# -- BPMN / Mermaid export -------------------------------------------------


def test_bpmn_xml_is_well_formed_and_complete():
    scheme = build_default_schemes()["incident"]
    xml = to_bpmn_xml(scheme)
    root = ET.fromstring(xml)  # raises on malformed XML

    tasks = root.findall(".//bpmn:userTask", BPMN_NS)
    assert len(tasks) == len(scheme.statuses)

    start_events = root.findall(".//bpmn:startEvent", BPMN_NS)
    assert len(start_events) == 1
    assert root.findall(".//bpmn:endEvent", BPMN_NS)  # at least one terminal

    # Layout interchange present so it renders in bpmn.io without manual layout.
    assert root.findall(".//bpmndi:BPMNShape", BPMN_NS)
    assert root.findall(".//bpmndi:BPMNEdge", BPMN_NS)


def test_bpmn_escapes_special_characters():
    scheme = (
        WorkflowScheme("amp", "A & B <Test>")
        .add_status("s", "Start & Go", StatusCategory.TODO, initial=True)
        .add_status("d", "Done", StatusCategory.DONE)
        .add_transition("t", "Move >", "d", ["s"])
    )
    xml = to_bpmn_xml(scheme)
    ET.fromstring(xml)  # must stay well-formed despite & < > in names


def test_mermaid_contains_states_and_transitions():
    scheme = build_default_schemes()["incident"]
    mermaid = to_mermaid(scheme)
    assert mermaid.startswith("stateDiagram-v2")
    assert "[*] --> open" in mermaid
    assert "Start Progress" in mermaid


# -- request lifecycle -----------------------------------------------------


def _desk(now: float = 1000.0) -> ServiceDesk:
    return ServiceDesk(clock=lambda: now)


def test_create_request_sets_initial_status_and_sla():
    desk = _desk()
    request = desk.create_request(
        type=RequestType.INCIDENT, summary="DB down", priority=Priority.CRITICAL, reporter="ann"
    )
    assert request.key == "REQ-1"
    assert request.status_id == "open"
    # critical → 15 min response, 240 min resolution from the standard policy
    assert request.sla_response_due == 1000.0 + 15 * 60
    assert request.sla_resolution_due == 1000.0 + 240 * 60
    assert request.history[0].kind == "created"


def test_full_incident_lifecycle_with_post_functions():
    desk = _desk()
    request = desk.create_request(type=RequestType.INCIDENT, summary="API 5xx")
    desk.transition(request.key, "triage", actor="ann", actor_role="agent")
    # 'start' is gated on is_agent and auto-assigns the actor.
    desk.transition(request.key, "start", actor="bob", actor_role="agent")
    # 'resolve' requires a resolution; supplying it satisfies the condition.
    resolved = desk.transition(request.key, "resolve", actor="bob", resolution="Restarted node")
    assert resolved.status_id == "resolved"
    assert resolved.assignee == "bob"
    assert resolved.resolved_at == 1000.0
    assert resolved.resolution == "Restarted node"


def test_resolve_without_resolution_blocked():
    desk = _desk()
    request = desk.create_request(type=RequestType.INCIDENT, summary="x")
    desk.transition(request.key, "triage", actor="ann", actor_role="agent")
    desk.transition(request.key, "start", actor="ann", actor_role="agent")
    with pytest.raises(WorkflowError):
        desk.transition(request.key, "resolve", actor="ann")  # no resolution set


def test_global_cancel_from_any_status():
    desk = _desk()
    request = desk.create_request(type=RequestType.INCIDENT, summary="x")
    cancelled = desk.transition(request.key, "cancel", actor="ann")
    assert cancelled.status_id == "cancelled"


def test_assign_field_edit():
    desk = _desk()
    request = desk.create_request(type=RequestType.INCIDENT, summary="x")
    updated = desk.assign(request.key, "carol", actor="lead")
    assert updated.assignee == "carol"
    assert updated.history[-1].kind == "assigned"


def test_change_management_requires_approval():
    desk = _desk()
    request = desk.create_request(type=RequestType.CHANGE, summary="Upgrade cluster")
    desk.transition(request.key, "submit", actor="dev")
    with pytest.raises(WorkflowError):
        desk.transition(request.key, "approve", actor="mgr", actor_role="manager")  # not approved
    approved = desk.transition(
        request.key, "approve", actor="mgr", actor_role="manager", approved=True
    )
    assert approved.status_id == "approved"


def test_queue_summary_counts_and_breaches():
    desk = ServiceDesk(clock=lambda: 1_000_000.0)
    desk.sla = SlaPolicy(targets={"medium": (1, 1)})  # 1-minute targets to force a breach
    desk.create_request(type=RequestType.INCIDENT, summary="old", priority=Priority.MEDIUM)
    # Advance the clock past the SLA windows.
    desk._clock = lambda: 1_000_000.0 + 10_000
    summary = desk.queue_summary()
    assert summary["total"] == 1
    assert summary["open"] == 1
    assert summary["by_category"]["todo"] == 1
    assert summary["sla_response_breaches"] == 1
    assert summary["sla_resolution_breaches"] == 1


# -- SQLite persistence ----------------------------------------------------


def test_sqlite_persistence_survives_new_instance(tmp_path):
    db_path = str(tmp_path / "itsm.db")
    desk = ServiceDesk(database=Database(db_path), clock=lambda: 1000.0)
    request = desk.create_request(type=RequestType.INCIDENT, summary="DB down", reporter="ann")
    desk.transition(request.key, "triage", actor="ann", actor_role="agent")

    # A fresh ServiceDesk over the same database file must see the persisted request.
    desk2 = ServiceDesk(database=Database(db_path), clock=lambda: 2000.0)
    loaded = desk2.get(request.key)
    assert loaded.status_id == "triaged"
    assert loaded.summary == "DB down"
    assert loaded.reporter == "ann"
    assert any(event.kind == "transition" for event in loaded.history)


def test_sqlite_key_sequence_is_monotonic(tmp_path):
    db_path = str(tmp_path / "itsm.db")
    desk = ServiceDesk(database=Database(db_path), project_prefix="INC", clock=lambda: 1.0)
    a = desk.create_request(type=RequestType.INCIDENT, summary="one")
    b = desk.create_request(type=RequestType.INCIDENT, summary="two")
    assert a.key == "INC-1"
    assert b.key == "INC-2"
    # Sequence continues across a new ServiceDesk on the same file.
    desk2 = ServiceDesk(database=Database(db_path), project_prefix="INC", clock=lambda: 2.0)
    c = desk2.create_request(type=RequestType.INCIDENT, summary="three")
    assert c.key == "INC-3"


def test_sqlite_repository_lists_in_creation_order(tmp_path):
    repo = SqliteRequestRepository(Database(str(tmp_path / "itsm.db")))
    desk = ServiceDesk(repository=repo, clock=lambda: 5.0)
    desk.create_request(type=RequestType.INCIDENT, summary="first")
    desk.create_request(type=RequestType.CHANGE, summary="second")
    keys = [r.key for r in repo.list_all()]
    assert keys == ["REQ-1", "REQ-2"]


# -- PostgreSQL storage ----------------------------------------------------
# Integration tests run only when ARCHUB_ITSM_PG_DSN points at a reachable
# PostgreSQL and the optional ``psycopg`` driver is installed; otherwise they skip.

_PG_DSN = os.environ.get("ARCHUB_ITSM_PG_DSN")
_HAS_PSYCOPG = importlib.util.find_spec("psycopg") is not None
_requires_pg = pytest.mark.skipif(
    not (_PG_DSN and _HAS_PSYCOPG),
    reason="set ARCHUB_ITSM_PG_DSN and install psycopg to run PostgreSQL tests",
)


def test_postgres_database_holds_dsn():
    db = PostgresDatabase("postgresql://localhost/itsm")
    assert db.dsn == "postgresql://localhost/itsm"


@pytest.mark.skipif(_HAS_PSYCOPG, reason="psycopg installed; driver-missing path not applicable")
def test_postgres_connect_without_driver_raises_helpful_error():
    with pytest.raises(RuntimeError, match="psycopg"):
        PostgresDatabase("postgresql://localhost/itsm").connect()


@pytest.fixture
def pg_repo():
    assert _PG_DSN is not None
    db = PostgresDatabase(_PG_DSN)
    conn = db.connect()
    try:
        conn.execute("DROP TABLE IF EXISTS itsm_request")
        conn.execute("DROP TABLE IF EXISTS itsm_request_seq")
        conn.commit()
    finally:
        conn.close()
    return PostgresRequestRepository(db)


@_requires_pg
def test_postgres_persistence_survives_new_instance(pg_repo):
    assert _PG_DSN is not None
    desk = ServiceDesk(repository=pg_repo, clock=lambda: 1000.0)
    request = desk.create_request(type=RequestType.INCIDENT, summary="DB down", reporter="ann")
    desk.transition(request.key, "triage", actor="ann", actor_role="agent")

    desk2 = ServiceDesk(
        repository=PostgresRequestRepository(PostgresDatabase(_PG_DSN)), clock=lambda: 2000.0
    )
    loaded = desk2.get(request.key)
    assert loaded.status_id == "triaged"
    assert loaded.summary == "DB down"
    assert loaded.reporter == "ann"
    assert any(event.kind == "transition" for event in loaded.history)


@_requires_pg
def test_postgres_key_sequence_is_monotonic(pg_repo):
    desk = ServiceDesk(repository=pg_repo, project_prefix="INC", clock=lambda: 1.0)
    a = desk.create_request(type=RequestType.INCIDENT, summary="one")
    b = desk.create_request(type=RequestType.INCIDENT, summary="two")
    assert (a.key, b.key) == ("INC-1", "INC-2")


def test_build_repository_defaults_to_sqlite(tmp_path):
    from archub_cms.extensibility.example_plugins.itsm.plugin import _build_repository

    repo = _build_repository({"db_path": str(tmp_path / "itsm.db")})
    assert isinstance(repo, SqliteRequestRepository)


def test_build_repository_postgres_requires_dsn(monkeypatch):
    from archub_cms.extensibility.example_plugins.itsm.plugin import _build_repository

    monkeypatch.delenv("ARCHUB_ITSM_PG_DSN", raising=False)
    with pytest.raises(RuntimeError, match="dsn"):
        _build_repository({"storage": "postgres"})


# -- plugin wiring through the host ----------------------------------------


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def host(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    get_archub_cms_service()
    return PluginHost().load()


def test_plugin_loads_with_all_extensions(host):
    report = host.report()
    assert "archub.itsm.service_desk" in {p["plugin_id"] for p in report["loaded"]}
    assert "itsm.transition" in host.workflow_actions
    assert "bpmn" in host.macros
    assert "itsm_queue" in host.dashboard_widgets
    assert "itsm.log_request" in host.page_actions
    assert "itsm.cloud" in host.connectors
    assert "itsm.triage" in host.llm_tools


def test_plugin_uses_sqlite_repository(host):
    plugin = host.plugin_instance("archub.itsm.service_desk")
    assert isinstance(plugin.desk.repository, SqliteRequestRepository)


def test_bpmn_macro_renders_through_host(host):
    rendered = host.render("{{bpmn scheme=incident}}")
    assert "```mermaid" in rendered
    assert "stateDiagram-v2" in rendered


def test_workflow_action_drives_request(host):
    plugin = host.plugin_instance("archub.itsm.service_desk")
    request = plugin.desk.create_request(type=RequestType.INCIDENT, summary="net down")
    action = host.workflow_actions["itsm.transition"]
    ctx = {"request": request.key, "transition": "triage", "actor": "ann", "actor_role": "agent"}
    assert action.can_execute(ctx) is True
    result = action.execute(ctx)
    assert result["ok"] is True
    assert result["request"]["status_id"] == "triaged"


def test_cloud_connector_pulls_alerts_as_incidents(host):
    connector = host.connectors["itsm.cloud"]
    created = connector.sync_pull(
        {
            "alerts": [
                {"title": "CPU high", "severity": "critical", "service": "compute", "region": "eu"},
                {"title": "Disk warn", "severity": "warning"},
            ]
        }
    )
    assert len(created) == 2
    assert created[0]["priority"] == "critical"
    assert connector.sync_push([{"key": "REQ-1"}, {"no_key": True}]) == 1


def test_triage_tool_classifies_offline(host):
    out = host.run_tool("itsm.triage", {"text": "Production database is down with 5xx errors"})
    assert "type=incident" in out
    assert "priority=critical" in out


def test_log_request_page_action(host):
    action = host.page_actions["itsm.log_request"]
    result = action.execute(
        {"title": "Need more quota", "type": "service_request", "actor": "dev", "service": "s3"}
    )
    assert result["action"] == "request_logged"
    assert result["request"]["type"] == "service_request"


def test_cloud_resource_roundtrip():
    res = CloudResource(provider="aws", service="ec2", region="us-east-1", resource_id="i-123")
    assert res.as_dict()["resource_id"] == "i-123"
