"""Governance repository adapter mapping legacy permission/access reads."""

from __future__ import annotations

__all__ = ["CmsGovernanceRepository"]

from archub_cms.domain.governance.access import AccessPolicy, AccessRule
from archub_cms.domain.governance.permission import PermissionRule
from archub_cms.services.cms import (
    ArcHubCMSService,
    ContentAccessRule,
    ContentPermissionRule,
    get_archub_cms_service,
)


def _policy(value: str) -> AccessPolicy:
    try:
        return AccessPolicy(value)
    except ValueError:
        return AccessPolicy.PUBLIC


def _permission(rule: ContentPermissionRule) -> PermissionRule:
    return PermissionRule(
        rule_id=rule.rule_id,
        subject=rule.subject,
        actions=tuple(rule.actions),
        scope_node_id=rule.scope_node_id,
        include_descendants=rule.include_descendants,
        note=rule.note,
    )


def _access(rule: ContentAccessRule) -> AccessRule:
    return AccessRule(
        node_id=rule.node_id,
        policy=_policy(rule.policy),
        member_groups=tuple(rule.member_groups),
        include_descendants=rule.include_descendants,
        login_path=rule.login_path,
        denied_path=rule.denied_path,
        note=rule.note,
    )


class CmsGovernanceRepository:
    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def list_permissions(self, *, limit: int = 100) -> list[PermissionRule]:
        return [_permission(r) for r in self._cms.list_content_permissions(limit=limit)]

    def list_access_rules(self, *, limit: int = 100) -> list[AccessRule]:
        return [_access(r) for r in self._cms.list_public_access_rules(limit=limit)]

    def get_access_rule(self, node_id: str, *, inherited: bool = True) -> AccessRule | None:
        found = self._cms.get_public_access_rule(node_id, inherited=inherited)
        return _access(found) if found is not None else None
