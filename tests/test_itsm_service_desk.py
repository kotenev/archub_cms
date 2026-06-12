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
    RequestRepository,
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
from archub_cms.extensibility.platform_adapter import (
    PluginAuditLog,
    PluginPlatformAdapter,
    PostgresPluginStore,
    SQLitePluginStore,
)
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.plugins.itsm_request_repository import (
    PostgresRequestRepository,
    SqliteRequestRepository,
)
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service
from archub_cms.settings import ArcHubSettings

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


def _audit_log(tmp_path) -> PluginAuditLog:
    return PluginAuditLog(Database(str(tmp_path / "plugin-audit.db")))


def _sqlite_repo(tmp_path, *, db_name: str = "itsm.db") -> SqliteRequestRepository:
    return SqliteRequestRepository(
        SQLitePluginStore(
            plugin_id="test.itsm",
            database=Database(str(tmp_path / db_name)),
            audit_log=_audit_log(tmp_path),
        )
    )


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
    db_path = tmp_path / "itsm.db"
    audit_log = _audit_log(tmp_path)
    repo = SqliteRequestRepository(
        SQLitePluginStore(
            plugin_id="test.itsm",
            database=Database(db_path),
            audit_log=audit_log,
        )
    )
    desk = ServiceDesk(repository=repo, clock=lambda: 1000.0)
    request = desk.create_request(type=RequestType.INCIDENT, summary="DB down", reporter="ann")
    desk.transition(request.key, "triage", actor="ann", actor_role="agent")

    # A fresh ServiceDesk over the same database file must see the persisted request.
    repo2 = SqliteRequestRepository(
        SQLitePluginStore(
            plugin_id="test.itsm",
            database=Database(db_path),
            audit_log=audit_log,
        )
    )
    desk2 = ServiceDesk(repository=repo2, clock=lambda: 2000.0)
    loaded = desk2.get(request.key)
    assert loaded.status_id == "triaged"
    assert loaded.summary == "DB down"
    assert loaded.reporter == "ann"
    assert any(event.kind == "transition" for event in loaded.history)


def test_sqlite_key_sequence_is_monotonic(tmp_path):
    db_path = tmp_path / "itsm.db"
    audit_log = _audit_log(tmp_path)
    repo = SqliteRequestRepository(
        SQLitePluginStore(
            plugin_id="test.itsm",
            database=Database(db_path),
            audit_log=audit_log,
        )
    )
    desk = ServiceDesk(repository=repo, project_prefix="INC", clock=lambda: 1.0)
    a = desk.create_request(type=RequestType.INCIDENT, summary="one")
    b = desk.create_request(type=RequestType.INCIDENT, summary="two")
    assert a.key == "INC-1"
    assert b.key == "INC-2"
    # Sequence continues across a new ServiceDesk on the same file.
    repo2 = SqliteRequestRepository(
        SQLitePluginStore(
            plugin_id="test.itsm",
            database=Database(db_path),
            audit_log=audit_log,
        )
    )
    desk2 = ServiceDesk(repository=repo2, project_prefix="INC", clock=lambda: 2.0)
    c = desk2.create_request(type=RequestType.INCIDENT, summary="three")
    assert c.key == "INC-3"


def test_sqlite_repository_lists_in_creation_order(tmp_path):
    repo = _sqlite_repo(tmp_path)
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


def test_postgres_store_holds_dsn(tmp_path):
    store = PostgresPluginStore(
        plugin_id="test.itsm",
        dsn="postgresql://localhost/itsm",
        audit_log=_audit_log(tmp_path),
    )
    assert store.dsn == "postgresql://localhost/itsm"


@pytest.mark.skipif(_HAS_PSYCOPG, reason="psycopg installed; driver-missing path not applicable")
def test_postgres_connect_without_driver_raises_helpful_error(tmp_path):
    store = PostgresPluginStore(
        plugin_id="test.itsm",
        dsn="postgresql://localhost/itsm",
        audit_log=_audit_log(tmp_path),
    )
    with pytest.raises(RuntimeError, match="psycopg"):
        store.connect()


@pytest.fixture
def pg_repo(tmp_path):
    assert _PG_DSN is not None
    store = PostgresPluginStore(
        plugin_id="test.itsm",
        dsn=_PG_DSN,
        audit_log=_audit_log(tmp_path),
    )
    conn = store.connect()
    try:
        conn.execute("DROP TABLE IF EXISTS itsm_request")
        conn.execute("DROP TABLE IF EXISTS itsm_request_seq")
        conn.commit()
    finally:
        conn.close()
    return PostgresRequestRepository(store)


@_requires_pg
def test_postgres_persistence_survives_new_instance(pg_repo, tmp_path):
    assert _PG_DSN is not None
    desk = ServiceDesk(repository=pg_repo, clock=lambda: 1000.0)
    request = desk.create_request(type=RequestType.INCIDENT, summary="DB down", reporter="ann")
    desk.transition(request.key, "triage", actor="ann", actor_role="agent")

    assert _PG_DSN is not None
    desk2 = ServiceDesk(
        repository=PostgresRequestRepository(
            PostgresPluginStore(
                plugin_id="test.itsm",
                dsn=_PG_DSN,
                audit_log=_audit_log(tmp_path),
            )
        ),
        clock=lambda: 2000.0,
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

    platform = PluginPlatformAdapter(
        plugin_id="test.itsm",
        settings=ArcHubSettings(cms_db_path=tmp_path / "archub.db"),
    )
    repo = _build_repository({"db_path": str(tmp_path / "itsm.db")}, platform)
    assert isinstance(repo, SqliteRequestRepository)
    assert isinstance(repo, RequestRepository)
    actions = {entry.action for entry in platform.audit_log.query(plugin_id="test.itsm")}
    assert "adapter.sqlite.open" in actions
    assert "itsm.schema.ensure" in actions


def test_build_repository_postgres_requires_dsn(monkeypatch, tmp_path):
    from archub_cms.extensibility.example_plugins.itsm.plugin import _build_repository

    monkeypatch.delenv("ARCHUB_ITSM_PG_DSN", raising=False)
    platform = PluginPlatformAdapter(
        plugin_id="test.itsm",
        settings=ArcHubSettings(cms_db_path=tmp_path / "archub.db"),
    )
    with pytest.raises(RuntimeError, match="dsn"):
        _build_repository({"storage": "postgres"}, platform)


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


def test_plugin_repository_actions_are_audited(host):
    plugin = host.plugin_instance("archub.itsm.service_desk")
    plugin.desk.create_request(type=RequestType.INCIDENT, summary="audit me")

    actions = {
        entry.action
        for entry in host.audit_log.query(plugin_id="archub.itsm.service_desk", limit=100)
    }
    assert {
        "plugin.load.attempt",
        "plugin.setup.attempt",
        "itsm.setup",
        "extension.registered",
        "adapter.sqlite.open",
        "itsm.schema.ensure",
        "itsm.request.next_key",
        "itsm.request.save",
    } <= actions


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


# -- REST API endpoints ----------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)
    with TestClient(create_archub_app()) as test_client:
        yield test_client


def test_api_create_and_get_request(client):
    created = client.post(
        "/api/platform/itsm/requests",
        json={"type": "incident", "summary": "DB down", "priority": "critical", "reporter": "ann"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["key"] == "REQ-1"
    assert body["status_id"] == "open"
    assert body["priority"] == "critical"

    fetched = client.get("/api/platform/itsm/requests/REQ-1")
    assert fetched.status_code == 200
    assert fetched.json()["summary"] == "DB down"


def test_api_create_request_validation(client):
    assert client.post("/api/platform/itsm/requests", json={"type": "incident"}).status_code == 422
    bad_type = client.post("/api/platform/itsm/requests", json={"type": "bogus", "summary": "x"})
    assert bad_type.status_code == 422


def test_api_list_and_filter_requests(client):
    client.post("/api/platform/itsm/requests", json={"type": "incident", "summary": "a"})
    client.post("/api/platform/itsm/requests", json={"type": "change", "summary": "b"})
    everything = client.get("/api/platform/itsm/requests").json()
    assert everything["total"] == 2
    only_changes = client.get("/api/platform/itsm/requests", params={"type": "change"}).json()
    assert only_changes["total"] == 1
    assert only_changes["requests"][0]["type"] == "change"


def test_api_transitions_lifecycle(client):
    client.post("/api/platform/itsm/requests", json={"type": "incident", "summary": "API 5xx"})

    available = client.get("/api/platform/itsm/requests/REQ-1/transitions").json()
    assert "triage" in {t["id"] for t in available["transitions"]}

    moved = client.post(
        "/api/platform/itsm/requests/REQ-1/transitions",
        json={"transition": "triage", "actor": "ann", "actor_role": "agent"},
    )
    assert moved.status_code == 200
    assert moved.json()["status_id"] == "triaged"


def test_api_illegal_transition_conflicts(client):
    client.post("/api/platform/itsm/requests", json={"type": "incident", "summary": "x"})
    bad = client.post(
        "/api/platform/itsm/requests/REQ-1/transitions", json={"transition": "resolve"}
    )
    assert bad.status_code == 409


def test_api_unknown_request_is_404(client):
    assert client.get("/api/platform/itsm/requests/NOPE").status_code == 404
    missing = client.post(
        "/api/platform/itsm/requests/NOPE/transitions", json={"transition": "triage"}
    )
    assert missing.status_code == 404


def test_api_assign_request(client):
    client.post("/api/platform/itsm/requests", json={"type": "incident", "summary": "x"})
    assigned = client.post(
        "/api/platform/itsm/requests/REQ-1/assign", json={"assignee": "carol", "actor": "lead"}
    )
    assert assigned.status_code == 200
    assert assigned.json()["assignee"] == "carol"


def test_api_schemes_and_bpmn(client):
    schemes = client.get("/api/platform/itsm/schemes").json()
    keys = {s["key"] for s in schemes["schemes"]}
    # The best-practice ITIL library ships by default.
    assert {
        "incident",
        "major_incident",
        "problem",
        "service_request",
        "change",
        "standard_change",
        "emergency_change",
        "release",
        "event",
        "knowledge",
    } <= keys
    assert schemes["total"] == len(keys)
    assert all(s["valid"] for s in schemes["schemes"])

    detail = client.get("/api/platform/itsm/schemes/incident")
    assert detail.status_code == 200
    assert detail.json()["valid"] is True

    bpmn = client.get("/api/platform/itsm/schemes/incident/bpmn")
    assert bpmn.status_code == 200
    assert bpmn.headers["content-type"].startswith("application/xml")
    assert "<bpmn:definitions" in bpmn.text

    mermaid = client.get(
        "/api/platform/itsm/schemes/incident/bpmn", params={"format": "mermaid"}
    ).json()
    assert mermaid["diagram"].startswith("stateDiagram-v2")

    assert client.get("/api/platform/itsm/schemes/nope").status_code == 404


def test_api_queue_summary(client):
    client.post(
        "/api/platform/itsm/requests",
        json={"type": "incident", "summary": "x", "priority": "high"},
    )
    queue = client.get("/api/platform/itsm/queue").json()
    assert queue["total"] == 1
    assert queue["open"] == 1
    assert queue["by_priority"]["high"] == 1


def test_api_itsm_rbac_roles_and_dashboard(client):
    headers = {"Authorization": "Bearer demo-itsm-agent-token"}

    roles = client.get("/api/platform/itsm/rbac/roles", headers=headers)
    assert roles.status_code == 200
    body = roles.json()
    role_ids = {role["role_id"] for role in body["roles"]}
    assert "itil:service_desk_agent" in role_ids
    assert body["current_user"]["actor_role"] == "agent"

    dashboard = client.get("/admin/itsm", headers=headers)
    assert dashboard.status_code == 200
    assert "ArcHub ITSM" in dashboard.text


def test_api_itsm_requires_itil_role(client):
    denied = client.get(
        "/api/platform/itsm/queue",
        headers={"X-ArcHub-User": "viewer", "X-ArcHub-Admin": "0"},
    )
    assert denied.status_code == 403


def test_api_requester_can_create_but_not_assign(client):
    headers = {"Authorization": "Bearer demo-itsm-requester-token"}

    created = client.post(
        "/api/platform/itsm/requests",
        headers=headers,
        json={"type": "incident", "summary": "Laptop is down"},
    )
    assert created.status_code == 201
    assert created.json()["reporter"] == "requester"

    assigned = client.post(
        "/api/platform/itsm/requests/REQ-1/assign",
        headers=headers,
        json={"assignee": "agent"},
    )
    assert assigned.status_code == 403


def test_api_agent_role_drives_workflow_actor_role(client):
    agent_headers = {"Authorization": "Bearer demo-itsm-agent-token"}
    client.post(
        "/api/platform/itsm/requests",
        headers={"Authorization": "Bearer demo-itsm-requester-token"},
        json={"type": "incident", "summary": "API 5xx"},
    )

    triaged = client.post(
        "/api/platform/itsm/requests/REQ-1/transitions",
        headers=agent_headers,
        json={"transition": "triage"},
    )
    assert triaged.status_code == 200

    started = client.post(
        "/api/platform/itsm/requests/REQ-1/transitions",
        headers=agent_headers,
        json={"transition": "start"},
    )
    assert started.status_code == 200
    assert started.json()["status_id"] == "in_progress"
    assert started.json()["assignee"] == "agent"


def test_api_change_manager_can_create_and_approve_change(client):
    headers = {"Authorization": "Bearer demo-itsm-change-manager-token"}

    created = client.post(
        "/api/platform/itsm/requests",
        headers=headers,
        json={"type": "change", "summary": "Upgrade cluster"},
    )
    assert created.status_code == 201

    submitted = client.post(
        "/api/platform/itsm/requests/REQ-1/transitions",
        headers=headers,
        json={"transition": "submit"},
    )
    assert submitted.status_code == 200

    approved = client.post(
        "/api/platform/itsm/requests/REQ-1/transitions",
        headers=headers,
        json={"transition": "approve", "approved": True},
    )
    assert approved.status_code == 200
    assert approved.json()["status_id"] == "approved"


# -- ITIL: Service Catalog / SLA / CMDB / BPMN engine (unit) ----------------

from archub_cms.extensibility.example_plugins.itsm.bpmn import from_bpmn_xml  # noqa: E402
from archub_cms.extensibility.example_plugins.itsm.catalog import ServiceCatalog  # noqa: E402
from archub_cms.extensibility.example_plugins.itsm.cmdb import Cmdb  # noqa: E402
from archub_cms.extensibility.example_plugins.itsm.documents import (  # noqa: E402
    InMemoryDocumentRepository,
)
from archub_cms.extensibility.example_plugins.itsm.itsm_service import (  # noqa: E402
    ItsmService,
    SchemeValidationError,
)
from archub_cms.extensibility.example_plugins.itsm.repository import (  # noqa: E402
    InMemoryRequestRepository,
)
from archub_cms.extensibility.example_plugins.itsm.sla import SlaRegistry  # noqa: E402


def _doc() -> InMemoryDocumentRepository:
    return InMemoryDocumentRepository()


def test_bpmn_roundtrip_is_lossless_for_default_schemes():
    for key, scheme in build_default_schemes().items():
        back = from_bpmn_xml(to_bpmn_xml(scheme))
        assert back.key == key
        assert set(back.statuses) == set(scheme.statuses)
        assert back.initial_status_id == scheme.initial_status_id
        assert {s.category for s in back.statuses.values()} == {
            s.category for s in scheme.statuses.values()
        }
        assert set(back.transitions) == set(scheme.transitions)
        for tid, transition in scheme.transitions.items():
            assert back.transitions[tid].to_status == transition.to_status
            assert back.transitions[tid].is_global == transition.is_global
        assert back.is_valid


def test_itil_default_scheme_library_is_complete_and_valid():
    schemes = build_default_schemes()
    expected = {
        "incident",
        "major_incident",
        "problem",
        "service_request",
        "change",
        "standard_change",
        "emergency_change",
        "release",
        "event",
        "knowledge",
    }
    assert expected <= set(schemes)
    for key, scheme in schemes.items():
        assert scheme.validate() == [], (key, scheme.validate())


def test_problem_requests_use_the_problem_scheme():
    desk = ServiceDesk(repository=InMemoryRequestRepository(), clock=lambda: 1.0)
    request = desk.create_request(type=RequestType.PROBLEM, summary="recurring outages")
    assert request.scheme_key == "problem"
    assert request.status_id == "new"


def test_problem_management_lifecycle():
    desk = ServiceDesk(repository=InMemoryRequestRepository(), clock=lambda: 1.0)
    req = desk.create_request(type=RequestType.PROBLEM, summary="root cause unknown")
    desk.transition(req.key, "investigate", actor="ann", actor_role="agent")
    desk.transition(req.key, "identify", actor="ann", actor_role="agent")
    desk.transition(req.key, "raise_change", actor="mgr", actor_role="manager")
    resolved = desk.transition(req.key, "resolve", actor="ann", resolution="patch deployed")
    assert resolved.status_id == "resolved"
    assert desk.transition(req.key, "close", actor="ann").status_id == "closed"


def test_emergency_change_requires_ecab_approval():
    desk = ServiceDesk(repository=InMemoryRequestRepository(), clock=lambda: 1.0)
    req = desk.create_request(
        type=RequestType.CHANGE, summary="prod hotfix", scheme_key="emergency_change"
    )
    desk.transition(req.key, "submit", actor="dev")
    with pytest.raises(WorkflowError):  # ECAB approval gate not satisfied
        desk.transition(req.key, "approve", actor="mgr", actor_role="manager")
    approved = desk.transition(req.key, "approve", actor="mgr", actor_role="manager", approved=True)
    assert approved.status_id == "approved"


def test_workflow_scheme_from_dict_roundtrip():
    for key, scheme in build_default_schemes().items():
        back = WorkflowScheme.from_dict(scheme.as_dict())
        assert back.key == key
        assert set(back.statuses) == set(scheme.statuses)
        assert back.initial_status_id == scheme.initial_status_id
        assert set(back.transitions) == set(scheme.transitions)
        for tid, transition in scheme.transitions.items():
            assert back.transitions[tid].to_status == transition.to_status
            assert back.transitions[tid].is_global == transition.is_global
        assert back.is_valid


def test_bpmn_import_of_handwritten_process():
    xml = """<?xml version="1.0"?>
    <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
      <bpmn:process id="approval">
        <bpmn:startEvent id="s" />
        <bpmn:userTask id="open" name="Open" />
        <bpmn:userTask id="done" name="Done" />
        <bpmn:endEvent id="e" />
        <bpmn:sequenceFlow id="f0" sourceRef="s" targetRef="open" />
        <bpmn:sequenceFlow id="f1" name="Finish" sourceRef="open" targetRef="done" />
        <bpmn:sequenceFlow id="f2" sourceRef="done" targetRef="e" />
      </bpmn:process>
    </bpmn:definitions>"""
    scheme = from_bpmn_xml(xml)
    assert scheme.key == "approval"
    assert scheme.initial_status_id == "open"
    assert scheme.statuses["done"].is_done  # flows into an end event → terminal
    assert scheme.is_valid
    assert scheme.apply("open", "f1").to_status == "done"


def test_bpmn_import_rejects_xml_without_tasks():
    with pytest.raises(ValueError):
        from_bpmn_xml(
            "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'/>"
        )


def test_service_catalog_crud():
    catalog = ServiceCatalog(_doc(), clock=lambda: 1.0)
    svc = catalog.create(name="Managed PostgreSQL", category="database", owner="dba")
    assert svc.id.startswith("svc-")
    assert catalog.get(svc.id).name == "Managed PostgreSQL"
    catalog.update(svc.id, lifecycle="deprecated")
    assert catalog.get(svc.id).lifecycle.value == "deprecated"
    assert [s.id for s in catalog.list(category="database")] == [svc.id]
    assert catalog.delete(svc.id) is True
    assert catalog.find(svc.id) is None


def test_sla_definition_to_policy():
    registry = SlaRegistry(_doc(), clock=lambda: 1.0)
    gold = registry.create(name="Gold", targets={"high": [10, 60], "low": [240, 1440]})
    policy = registry.policy_for(gold.id)
    assert policy is not None
    assert policy.response_minutes(Priority.HIGH) == 10
    assert policy.resolution_minutes(Priority.HIGH) == 60


def test_cmdb_items_relationships_and_impact():
    cmdb = Cmdb(_doc(), _doc(), clock=lambda: 1.0)
    db = cmdb.add_item(name="pg-prod", ci_type="database")
    app = cmdb.add_item(name="checkout", ci_type="application")
    web = cmdb.add_item(name="storefront", ci_type="application")
    cmdb.relate(app.id, db.id, "depends_on")
    cmdb.relate(web.id, app.id, "depends_on")
    impact = cmdb.impact(db.id)
    # both the app and the web tier are (transitively) impacted if the DB fails
    assert impact["impacted_count"] == 2
    impacted_ids = {ci["id"] for ci in impact["impacted"]}
    assert impacted_ids == {app.id, web.id}
    # deleting a CI drops its relationships
    cmdb.delete_item(app.id)
    assert cmdb.impact(db.id)["impacted_count"] == 0


def test_cmdb_rejects_self_relationship():
    cmdb = Cmdb(_doc(), _doc(), clock=lambda: 1.0)
    ci = cmdb.add_item(name="solo")
    with pytest.raises(ValueError):
        cmdb.relate(ci.id, ci.id, "depends_on")


def _itsm_service(now: float = 1000.0) -> ItsmService:
    return ItsmService(
        desk=ServiceDesk(repository=InMemoryRequestRepository(), clock=lambda: now),
        catalog=ServiceCatalog(_doc(), clock=lambda: now),
        sla=SlaRegistry(_doc(), clock=lambda: now),
        cmdb=Cmdb(_doc(), _doc(), clock=lambda: now),
        scheme_repo=_doc(),
        link_repo=_doc(),
        clock=lambda: now,
    )


def test_itsm_service_applies_service_sla_and_records_impact():
    itsm = _itsm_service(now=1000.0)
    gold = itsm.sla.create(name="Gold", targets={"high": [10, 60]})
    svc = itsm.catalog.create(name="Managed PG", category="database", sla_id=gold.id)
    db = itsm.cmdb.add_item(name="pg-prod", ci_type="database", service_id=svc.id)
    app = itsm.cmdb.add_item(name="checkout", ci_type="application")
    itsm.cmdb.relate(app.id, db.id, "depends_on")

    request = itsm.log_request(
        type=RequestType.INCIDENT,
        summary="pg down",
        priority=Priority.HIGH,
        service_id=svc.id,
        ci_ids=(db.id,),
    )
    # Gold SLA (high): 10 min response, 60 min resolution — applied, not the default.
    assert request.sla_response_due - request.created_at == 10 * 60
    assert request.sla_resolution_due - request.created_at == 60 * 60

    impact = itsm.request_impact(request.key)
    assert impact["service"]["id"] == svc.id
    assert impact["impacted_count"] == 1
    assert impact["impacted"][0]["id"] == app.id


def test_itsm_service_imports_and_persists_bpmn_scheme():
    itsm = _itsm_service()
    base = build_default_schemes()["incident"]
    xml = to_bpmn_xml(base)
    scheme = itsm.import_bpmn_scheme(xml, key="custom_incident", name="Custom Incident")
    assert scheme.key == "custom_incident"
    assert "custom_incident" in itsm.desk.schemes  # registered on the desk
    assert "custom_incident" in itsm.custom_scheme_keys()  # persisted

    # A fresh facade over the same document store reloads the persisted scheme.
    reloaded = ItsmService(
        desk=ServiceDesk(repository=InMemoryRequestRepository()),
        catalog=itsm.catalog,
        sla=itsm.sla,
        cmdb=itsm.cmdb,
        scheme_repo=itsm._schemes,
        link_repo=itsm._links,
    )
    assert "custom_incident" in reloaded.desk.schemes


def test_itsm_service_rejects_invalid_bpmn_scheme():
    itsm = _itsm_service()
    xml = """<?xml version="1.0"?>
    <bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
      <bpmn:process id="broken">
        <bpmn:userTask id="a" name="A" />
        <bpmn:userTask id="island" name="Island" />
        <bpmn:sequenceFlow id="f" sourceRef="a" targetRef="a" />
      </bpmn:process>
    </bpmn:definitions>"""
    with pytest.raises(SchemeValidationError):
        itsm.import_bpmn_scheme(xml)


def test_document_repository_sqlite_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "docs.db"))
    from archub_cms.extensibility.platform_adapter import PluginPlatformAdapter

    adapter = PluginPlatformAdapter(plugin_id="test.itsm")
    repo = adapter.document_repository("itsm_catalog", {})
    repo.upsert("a", {"id": "a", "name": "X", "created_at": 1.0, "updated_at": 1.0})
    assert repo.get("a")["name"] == "X"

    # A fresh repository over the same database/collection sees the document.
    repo2 = adapter.document_repository("itsm_catalog", {})
    assert [d["id"] for d in repo2.list_all()] == ["a"]
    # A different collection is isolated.
    other = adapter.document_repository("itsm_sla", {})
    assert other.list_all() == []
    assert repo2.delete("a") is True
    assert repo2.get("a") is None


# -- ITIL REST API ---------------------------------------------------------


def test_api_catalog_crud(client):
    created = client.post(
        "/api/platform/itsm/catalog",
        json={"name": "Object Storage", "category": "storage", "owner": "sre"},
    )
    assert created.status_code == 201
    service_id = created.json()["id"]

    listing = client.get("/api/platform/itsm/catalog", params={"category": "storage"}).json()
    assert listing["total"] == 1

    updated = client.put(
        f"/api/platform/itsm/catalog/{service_id}", json={"lifecycle": "deprecated"}
    )
    assert updated.json()["lifecycle"] == "deprecated"
    assert client.delete(f"/api/platform/itsm/catalog/{service_id}").json()["deleted"] is True
    assert client.get(f"/api/platform/itsm/catalog/{service_id}").status_code == 404


def test_api_sla_drives_request_due_times(client):
    sla = client.post(
        "/api/platform/itsm/sla", json={"name": "Gold", "targets": {"high": [10, 60]}}
    ).json()
    svc = client.post(
        "/api/platform/itsm/catalog",
        json={"name": "Managed PG", "category": "database", "sla_id": sla["id"]},
    ).json()
    request = client.post(
        "/api/platform/itsm/requests",
        json={
            "type": "incident",
            "summary": "pg down",
            "priority": "high",
            "service_id": svc["id"],
        },
    ).json()
    # Gold SLA applied via the linked service (60-minute resolution target).
    assert request["sla_resolution_due"] - request["created_at"] == 60 * 60


def test_api_cmdb_items_and_impact(client):
    db = client.post(
        "/api/platform/itsm/cmdb/items", json={"name": "pg-prod", "ci_type": "database"}
    ).json()
    app = client.post(
        "/api/platform/itsm/cmdb/items", json={"name": "checkout", "ci_type": "application"}
    ).json()
    rel = client.post(
        "/api/platform/itsm/cmdb/relationships",
        json={"source_id": app["id"], "target_id": db["id"], "type": "depends_on"},
    )
    assert rel.status_code == 201

    impact = client.get(f"/api/platform/itsm/cmdb/items/{db['id']}/impact").json()
    assert impact["impacted_count"] == 1
    assert impact["impacted"][0]["id"] == app["id"]

    self_rel = client.post(
        "/api/platform/itsm/cmdb/relationships",
        json={"source_id": db["id"], "target_id": db["id"]},
    )
    assert self_rel.status_code == 422


def test_api_request_impact_endpoint(client):
    svc = client.post(
        "/api/platform/itsm/catalog", json={"name": "Compute", "category": "compute"}
    ).json()
    ci = client.post(
        "/api/platform/itsm/cmdb/items", json={"name": "vm-1", "ci_type": "server"}
    ).json()
    request = client.post(
        "/api/platform/itsm/requests",
        json={
            "type": "incident",
            "summary": "vm crash",
            "service_id": svc["id"],
            "ci_ids": [ci["id"]],
        },
    ).json()
    impact = client.get(f"/api/platform/itsm/requests/{request['key']}/impact").json()
    assert impact["service"]["id"] == svc["id"]
    assert {c["id"] for c in impact["configuration_items"]} == {ci["id"]}


def test_api_bpmn_engine_import_and_delete(client):
    # Export the built-in incident scheme, then re-import it under a new key.
    exported = client.get("/api/platform/itsm/schemes/incident/bpmn")
    assert exported.status_code == 200
    imported = client.post(
        "/api/platform/itsm/schemes/import-bpmn",
        json={"bpmn": exported.text, "key": "custom_flow", "name": "Custom Flow"},
    )
    assert imported.status_code == 201
    assert imported.json()["key"] == "custom_flow"

    # The imported scheme is now a runnable, listed workflow scheme.
    schemes = {s["key"] for s in client.get("/api/platform/itsm/schemes").json()["schemes"]}
    assert "custom_flow" in schemes
    assert client.get("/api/platform/itsm/schemes/custom_flow/bpmn").status_code == 200

    # Custom schemes can be deleted; built-ins cannot.
    assert client.delete("/api/platform/itsm/schemes/custom_flow").json()["deleted"] is True
    assert client.delete("/api/platform/itsm/schemes/incident").status_code == 409


def test_api_bpmn_import_rejects_invalid_xml(client):
    bad = client.post("/api/platform/itsm/schemes/import-bpmn", json={"bpmn": "<not-bpmn/>"})
    assert bad.status_code == 422


def test_api_report_endpoint(client):
    client.post("/api/platform/itsm/catalog", json={"name": "S", "category": "x"})
    report = client.get("/api/platform/itsm/report").json()
    assert report["catalog"]["total"] == 1
    assert "queue" in report and "cmdb" in report


def test_api_management_requires_permission(client):
    # A viewer (read-only ITIL role) cannot create catalog entries.
    denied = client.post(
        "/api/platform/itsm/catalog",
        json={"name": "X", "category": "y"},
        headers={"X-ArcHub-User": "viewer", "X-ArcHub-Admin": "0"},
    )
    assert denied.status_code == 403


# -- Visual BPMN workflow editor (web) -------------------------------------


def test_api_workflow_editor_offline_by_default(client):
    # The offline editor plugin ships enabled, so the page renders in offline mode
    # with a self-hosted asset and NO CDN dependency.
    page = client.get("/admin/itsm/workflow")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    body = page.text
    assert 'data-mode="offline"' in body
    assert "ArcHubBpmnEditor" in body
    assert "/admin/itsm/workflow/assets/bpmn_editor.js" in body
    assert "unpkg.com/bpmn-js" not in body  # no CDN — fully offline
    assert "itsm-workflow-data" in body
    assert '"incident"' in body
    # Default identity is admin → editing enabled.
    assert 'data-can-edit="true"' in body


def test_api_workflow_editor_assets_served_offline(client):
    js = client.get("/admin/itsm/workflow/assets/bpmn_editor.js")
    assert js.status_code == 200
    assert js.headers["content-type"].startswith("application/javascript")
    assert "ArcHubBpmnEditor" in js.text
    css = client.get("/admin/itsm/workflow/assets/bpmn_editor.css")
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")
    # Unknown / traversal asset names are rejected.
    assert client.get("/admin/itsm/workflow/assets/nope.js").status_code == 404


def test_offline_editor_plugin_registered(client):
    extensions = client.get("/api/platform/extensions")
    # The editor plugin loaded as an EditorExt in the platform plugin host.
    report = client.get("/api/platform/plugins").json()
    assert "bpmn-offline" in report["editors"]
    assert extensions.status_code == 200


def test_api_workflow_editor_read_only_without_admin(client):
    # A service-desk agent has READ (can view) but not itsm:admin (cannot edit).
    headers = {"Authorization": "Bearer demo-itsm-agent-token"}
    page = client.get("/admin/itsm/workflow", headers=headers)
    assert page.status_code == 200
    assert 'data-can-edit="false"' in page.text


def test_api_create_scheme_from_json(client):
    # What the offline editor's "Save" does: POST the scheme as JSON; the engine
    # validates, registers and persists it as BPMN.
    created = client.post(
        "/api/platform/itsm/schemes",
        json={
            "key": "ticket_flow",
            "name": "Ticket Flow",
            "initial_status_id": "new",
            "statuses": [
                {"id": "new", "name": "New", "category": "todo"},
                {"id": "wip", "name": "Working", "category": "in_progress"},
                {"id": "closed", "name": "Closed", "category": "done"},
            ],
            "transitions": [
                {"id": "start", "name": "Start", "to_status": "wip", "from_statuses": ["new"]},
                {"id": "finish", "name": "Finish", "to_status": "closed", "from_statuses": ["wip"]},
            ],
        },
    )
    assert created.status_code == 201
    assert created.json()["valid"] is True
    # Registered → selectable and exportable as BPMN.
    schemes = {s["key"] for s in client.get("/api/platform/itsm/schemes").json()["schemes"]}
    assert "ticket_flow" in schemes
    assert client.get("/api/platform/itsm/schemes/ticket_flow/bpmn").status_code == 200


def test_api_create_scheme_invalid_returns_problems(client):
    bad = client.post(
        "/api/platform/itsm/schemes",
        json={
            "key": "broken",
            "name": "Broken",
            "statuses": [{"id": "a", "name": "A", "category": "todo"}],
        },
    )
    assert bad.status_code == 422
    assert "problems" in bad.json()["detail"]


def test_api_dashboard_links_to_workflow_editor(client):
    dashboard = client.get("/admin/itsm")
    assert dashboard.status_code == 200
    assert "/admin/itsm/workflow" in dashboard.text


def test_api_workflow_editor_save_roundtrip(client):
    # Mirrors what the editor's "Save" does: take the BPMN the canvas loaded and
    # POST it back to the engine, which validates and registers it as runnable.
    exported = client.get("/api/platform/itsm/schemes/incident/bpmn").text
    saved = client.post(
        "/api/platform/itsm/schemes/import-bpmn",
        json={"bpmn": exported, "key": "edited_incident", "name": "Edited Incident"},
    )
    assert saved.status_code == 201
    body = saved.json()
    assert body["key"] == "edited_incident"
    assert body["valid"] is True
    # It is now selectable in the editor's scheme list.
    schemes = {s["key"] for s in client.get("/api/platform/itsm/schemes").json()["schemes"]}
    assert "edited_incident" in schemes
