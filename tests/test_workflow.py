"""Tests for the workflow bounded context / state machine (Phase 8)."""

from __future__ import annotations

import pytest

from archub_cms.application.workflow_service import (
    WorkflowCommandService,
    get_archub_workflow_query_service,
)
from archub_cms.domain.workflow.workflow import (
    WORKFLOW_TRANSITIONS,
    Workflow,
    WorkflowState,
    WorkflowTransitionError,
)
from archub_cms.infrastructure.sqlite.workflow_repository import CmsWorkflowRepository
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def node(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    created = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Doc",
        slug="doc",
        payload={"title": "Doc"},
        created_by="t",
    )
    return cms, created.node_id


# --- domain: state machine -----------------------------------------------


def test_initial_state_and_allowed_transitions():
    w = Workflow(node_id="n")
    assert w.state is WorkflowState.DRAFT
    assert WorkflowState.IN_REVIEW in w.allowed_transitions()
    assert w.can_transition(WorkflowState.IN_REVIEW)
    assert not w.can_transition(WorkflowState.APPROVED)


def test_approval_flow_transitions():
    w = Workflow(node_id="n")
    w.transition(WorkflowState.IN_REVIEW)
    assert w.state is WorkflowState.IN_REVIEW
    w.transition(WorkflowState.APPROVED, assigned_to="lead")
    assert w.state is WorkflowState.APPROVED and w.assigned_to == "lead"
    w.transition(WorkflowState.PUBLISHED)
    assert w.state is WorkflowState.PUBLISHED


def test_illegal_transition_raises():
    w = Workflow(node_id="n")
    w.transition(WorkflowState.IN_REVIEW)
    with pytest.raises(WorkflowTransitionError):
        w.transition(WorkflowState.PUBLISHED)  # must be approved first


def test_changes_requested_loops_back():
    w = Workflow(node_id="n", state=WorkflowState.IN_REVIEW)
    w.transition(WorkflowState.CHANGES_REQUESTED)
    assert w.can_transition(WorkflowState.DRAFT)
    assert w.can_transition(WorkflowState.IN_REVIEW)


def test_transition_table_is_closed():
    # every target state referenced is itself a known state
    known = set(WorkflowState)
    for source, targets in WORKFLOW_TRANSITIONS.items():
        assert source in known
        assert targets <= known


# --- application service --------------------------------------------------


def test_command_transition_emits_event(node):
    cms, node_id = node
    fired: list[tuple[str, str]] = []
    get_event_bus().subscribe(
        "workflow.transitioned", lambda e: fired.append((e.metadata["from"], e.metadata["to"]))
    )
    cmd = WorkflowCommandService(cms=cms)
    cmd.transition(node_id, "in_review", actor="editor", assigned_to="rev")
    workflow = cmd.transition(node_id, "approved", actor="rev")
    assert workflow.state is WorkflowState.APPROVED
    assert fired == [("draft", "in_review"), ("in_review", "approved")]

    q = get_archub_workflow_query_service(cms=cms)
    assert q.get(node_id)["state"] == "approved"
    assert "published" in q.allowed_transitions(node_id)["allowed_transitions"]


def test_command_rejects_illegal_transition(node):
    cms, node_id = node
    cmd = WorkflowCommandService(cms=cms)
    cmd.transition(node_id, "in_review", actor="e")
    with pytest.raises(WorkflowTransitionError):
        cmd.transition(node_id, "published", actor="e")


def test_command_rejects_unknown_state(node):
    cms, node_id = node
    with pytest.raises(WorkflowTransitionError):
        WorkflowCommandService(cms=cms).transition(node_id, "bogus", actor="e")


def test_repository_defaults_to_draft(node):
    cms, node_id = node
    assert CmsWorkflowRepository(cms).get(node_id).state is WorkflowState.DRAFT


# --- endpoints ------------------------------------------------------------


def test_workflow_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    created = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="P",
        slug="p",
        payload={"title": "P"},
        created_by="t",
    )
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        state = client.get(f"/api/platform/workflow/{created.node_id}")
        assert state.status_code == 200
        assert state.json()["state"] == "draft"

        moved = client.post(
            f"/api/platform/workflow/{created.node_id}/transition",
            json={"to": "in_review", "actor": "editor"},
        )
        assert moved.status_code == 200
        assert moved.json()["state"] == "in_review"

        # illegal jump → 409
        bad = client.post(
            f"/api/platform/workflow/{created.node_id}/transition",
            json={"to": "published", "actor": "editor"},
        )
        assert bad.status_code == 409

        assert client.get("/api/platform/workflow/report").status_code == 200
