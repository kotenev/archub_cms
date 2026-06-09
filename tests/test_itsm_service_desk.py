"""Tests for the ITSM Service Desk plugin: workflow engine, BPMN export, tickets.

Covers the customizable Jira-style workflow engine, the BPMN 2.0 / Mermaid
serializers, the Service Desk ticket lifecycle with SLA + post-functions, and the
plugin loading end-to-end through the PluginHost with all six extensions wired.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest

from archub_cms.extensibility.example_plugins.itsm.bpmn import to_bpmn_xml, to_mermaid
from archub_cms.extensibility.example_plugins.itsm.service_desk import (
    ServiceDesk,
    build_default_schemes,
)
from archub_cms.extensibility.example_plugins.itsm.tickets import (
    CloudResource,
    Priority,
    SlaPolicy,
    TicketType,
)
from archub_cms.extensibility.example_plugins.itsm.workflow import (
    StatusCategory,
    WorkflowError,
    WorkflowScheme,
)
from archub_cms.extensibility.host import PluginHost
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


# -- ticket lifecycle ------------------------------------------------------


def _desk(now: float = 1000.0) -> ServiceDesk:
    return ServiceDesk(clock=lambda: now)


def test_create_ticket_sets_initial_status_and_sla():
    desk = _desk()
    ticket = desk.create_ticket(
        type=TicketType.INCIDENT, summary="DB down", priority=Priority.CRITICAL, reporter="ann"
    )
    assert ticket.key == "SD-1"
    assert ticket.status_id == "open"
    # critical → 15 min response, 240 min resolution from the standard policy
    assert ticket.sla_response_due == 1000.0 + 15 * 60
    assert ticket.sla_resolution_due == 1000.0 + 240 * 60
    assert ticket.history[0].kind == "created"


def test_full_incident_lifecycle_with_post_functions():
    desk = _desk()
    ticket = desk.create_ticket(type=TicketType.INCIDENT, summary="API 5xx")
    desk.transition(ticket.key, "triage", actor="ann", actor_role="agent")
    # 'start' is gated on is_agent and auto-assigns the actor.
    desk.transition(ticket.key, "start", actor="bob", actor_role="agent")
    assert ticket.status_id == "in_progress"
    assert ticket.assignee == "bob"
    # 'resolve' requires a resolution; supplying it satisfies the condition.
    desk.transition(ticket.key, "resolve", actor="bob", resolution="Restarted node")
    assert ticket.status_id == "resolved"
    assert ticket.resolved_at == 1000.0
    assert ticket.resolution == "Restarted node"


def test_resolve_without_resolution_blocked():
    desk = _desk()
    ticket = desk.create_ticket(type=TicketType.INCIDENT, summary="x")
    desk.transition(ticket.key, "triage", actor="ann", actor_role="agent")
    desk.transition(ticket.key, "start", actor="ann", actor_role="agent")
    with pytest.raises(WorkflowError):
        desk.transition(ticket.key, "resolve", actor="ann")  # no resolution set


def test_global_cancel_from_any_status():
    desk = _desk()
    ticket = desk.create_ticket(type=TicketType.INCIDENT, summary="x")
    desk.transition(ticket.key, "cancel", actor="ann")
    assert ticket.status_id == "cancelled"


def test_assign_field_edit():
    desk = _desk()
    ticket = desk.create_ticket(type=TicketType.INCIDENT, summary="x")
    desk.assign(ticket.key, "carol", actor="lead")
    assert ticket.assignee == "carol"
    assert ticket.history[-1].kind == "assigned"


def test_change_management_requires_approval():
    desk = _desk()
    ticket = desk.create_ticket(type=TicketType.CHANGE, summary="Upgrade cluster")
    desk.transition(ticket.key, "submit", actor="dev")
    with pytest.raises(WorkflowError):
        desk.transition(ticket.key, "approve", actor="mgr", actor_role="manager")  # not approved
    desk.transition(ticket.key, "approve", actor="mgr", actor_role="manager", approved=True)
    assert ticket.status_id == "approved"


def test_queue_summary_counts_and_breaches():
    desk = ServiceDesk(clock=lambda: 1_000_000.0)
    desk.sla = SlaPolicy(targets={"medium": (1, 1)})  # 1-minute targets to force a breach
    t = desk.create_ticket(type=TicketType.INCIDENT, summary="old", priority=Priority.MEDIUM)
    # Advance the clock past the SLA windows.
    desk._clock = lambda: 1_000_000.0 + 10_000
    summary = desk.queue_summary()
    assert summary["total"] == 1
    assert summary["open"] == 1
    assert summary["by_category"]["todo"] == 1
    assert summary["sla_response_breaches"] == 1
    assert summary["sla_resolution_breaches"] == 1
    assert t.assignee == ""


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
    assert "itsm.raise_ticket" in host.page_actions
    assert "itsm.cloud" in host.connectors
    assert "itsm.triage" in host.llm_tools


def test_bpmn_macro_renders_through_host(host):
    rendered = host.render("{{bpmn scheme=incident}}")
    assert "```mermaid" in rendered
    assert "stateDiagram-v2" in rendered


def test_workflow_action_drives_ticket(host):
    plugin = host.plugin_instance("archub.itsm.service_desk")
    ticket = plugin.desk.create_ticket(type=TicketType.INCIDENT, summary="net down")
    action = host.workflow_actions["itsm.transition"]
    ctx = {"ticket": ticket.key, "transition": "triage", "actor": "ann", "actor_role": "agent"}
    assert action.can_execute(ctx) is True
    result = action.execute(ctx)
    assert result["ok"] is True
    assert result["ticket"]["status_id"] == "triaged"


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
    assert connector.sync_push([{"key": "SD-1"}, {"no_key": True}]) == 1


def test_triage_tool_classifies_offline(host):
    out = host.run_tool("itsm.triage", {"text": "Production database is down with 5xx errors"})
    assert "type=incident" in out
    assert "priority=critical" in out


def test_raise_ticket_page_action(host):
    action = host.page_actions["itsm.raise_ticket"]
    result = action.execute(
        {"title": "Need more quota", "type": "service_request", "actor": "dev", "service": "s3"}
    )
    assert result["action"] == "ticket_created"
    assert result["ticket"]["type"] == "service_request"


def test_cloud_resource_roundtrip():
    res = CloudResource(provider="aws", service="ec2", region="us-east-1", resource_id="i-123")
    assert res.as_dict()["resource_id"] == "i-123"
