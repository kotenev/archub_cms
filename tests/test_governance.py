"""Tests for the governance context + pluggable auth (Phase 7)."""

from __future__ import annotations

import pytest

from archub_cms.application.governance_service import (
    AccessControlService,
    GovernanceCommandService,
    get_archub_governance_query_service,
)
from archub_cms.domain.governance.access import AccessPolicy, AccessRule
from archub_cms.domain.governance.permission import PermissionRule
from archub_cms.extensibility.host import PluginHost
from archub_cms.infrastructure.sqlite.governance_repository import CmsGovernanceRepository
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def cms(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    return get_archub_cms_service()


# --- domain: decision logic ----------------------------------------------


def test_permission_rule_grants_and_validation():
    rule = PermissionRule(rule_id="r", subject="user:bob", actions=("update", "publish"))
    assert rule.grants("update") and not rule.grants("delete")
    admin = PermissionRule(rule_id="a", subject="user:root", actions=("admin",))
    assert admin.grants("delete") and admin.is_admin
    bad = PermissionRule(rule_id="b", subject="", actions=("bogus",))
    errors = bad.validate()
    assert any("subject" in e for e in errors) and any("unknown actions" in e for e in errors)


def test_access_rule_decisions():
    public = AccessRule(node_id="n", policy=AccessPolicy.PUBLIC)
    assert public.permits(authenticated=False)

    auth = AccessRule(node_id="n", policy=AccessPolicy.AUTHENTICATED)
    assert not auth.permits(authenticated=False)
    assert auth.permits(authenticated=True)

    members = AccessRule(node_id="n", policy=AccessPolicy.MEMBERS, member_groups=("editors",))
    assert not members.permits(authenticated=True, groups=["readers"])
    assert members.permits(authenticated=True, groups=["EDITORS"])  # case-insensitive
    # members with no group gate → any authenticated user
    open_members = AccessRule(node_id="n", policy=AccessPolicy.MEMBERS)
    assert open_members.permits(authenticated=True)


# --- command + query + access control ------------------------------------


def test_grant_permission_emits_event_and_check(cms):
    fired: list[str] = []
    get_event_bus().subscribe(
        "governance.permission.granted", lambda e: fired.append(e.metadata["subject"])
    )
    cmd = GovernanceCommandService(cms=cms)
    rule = cmd.grant_permission(subject="editor", actions=["update"], actor="admin")
    assert rule.grants("update")
    assert fired and "editor" in fired[0]

    acl = AccessControlService(cms=cms)
    assert acl.can_perform(username="editor", is_admin=False, action="update")
    assert not acl.can_perform(username="nobody", is_admin=False, action="update")
    assert acl.can_perform(username="x", is_admin=True, action="delete")  # admin bypass


def test_set_access_rule_and_can_access(cms):
    node = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Members Only",
        slug="members-only",
        payload={"title": "Members Only"},
        created_by="t",
    )
    fired: list[str] = []
    get_event_bus().subscribe("governance.access.updated", lambda e: fired.append(e.aggregate_id))
    cmd = GovernanceCommandService(cms=cms)
    cmd.set_access_rule(
        node_id=node.node_id, policy="members", member_groups=["editors"], actor="admin"
    )
    assert fired == [node.node_id]

    acl = AccessControlService(cms=cms)
    assert acl.can_access(node.node_id, authenticated=False)["allowed"] is False
    assert acl.can_access(node.node_id, authenticated=True, groups=["editors"])["allowed"] is True


def test_invalid_grant_rejected(cms):
    cmd = GovernanceCommandService(cms=cms)
    with pytest.raises(ValueError):
        cmd.grant_permission(subject="", actions=[], actor="a")


def test_query_service_lists(cms):
    GovernanceCommandService(cms=cms).grant_permission(
        subject="editor", actions=["update"], actor="admin"
    )
    q = get_archub_governance_query_service(cms=cms)
    assert q.permissions()["total"] >= 1
    assert "update" in q.actions()
    assert "members" in q.policies()
    assert isinstance(CmsGovernanceRepository(cms).list_access_rules(), list)


# --- pluggable auth (AuthExt) --------------------------------------------


def test_access_control_identity_via_plugin(cms):
    host = PluginHost().load()
    assert "example.header_auth" in {p["plugin_id"] for p in host.report()["loaded"]}
    acl = AccessControlService(cms=cms, plugin_host=host)

    class Req:
        def __init__(self, headers):
            self.headers = headers

    admin = acl.identity(Req({"Authorization": "Bearer demo-admin-token"}))
    assert admin is not None and admin.is_admin
    assert acl.identity(Req({})) is None


# --- endpoints ------------------------------------------------------------


def test_governance_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        actions = client.get("/api/platform/governance/actions").json()
        assert "update" in actions["actions"] and "members" in actions["policies"]

        admin = client.get(
            "/api/platform/governance/whoami",
            headers={"Authorization": "Bearer demo-admin-token"},
        ).json()
        assert admin["authenticated"] and admin["is_admin"]

        anon = client.get("/api/platform/governance/whoami").json()
        assert anon["authenticated"] is False

        check = client.post(
            "/api/platform/governance/check",
            json={"username": "x", "is_admin": True, "action": "delete"},
        ).json()
        assert check["allowed"] is True
