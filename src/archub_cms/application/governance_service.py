"""Application service for the governance context (RBAC + public access).

``GovernanceQueryService`` reads rules; ``GovernanceCommandService`` grants
permissions / sets access rules (validating domain aggregates, delegating
persistence, emitting events); ``AccessControlService`` makes decisions —
delegating scope-aware permission checks to the legacy service and using the
``AccessRule`` aggregate for the public-access decision. Identity can be resolved
through auth plugins via the plugin host.
"""

from __future__ import annotations

__all__ = [
    "AccessControlService",
    "GovernanceCommandService",
    "GovernanceQueryService",
    "get_archub_governance_query_service",
]

from collections.abc import Iterable
from typing import Any

from archub_cms.domain.governance.access import AccessPolicy, AccessRule
from archub_cms.domain.governance.permission import PERMISSION_ACTIONS, PermissionRule
from archub_cms.domain.governance.repository import GovernanceRepository
from archub_cms.infrastructure.sqlite.governance_repository import CmsGovernanceRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class GovernanceQueryService:
    def __init__(self, repository: GovernanceRepository) -> None:
        self._repo = repository

    def actions(self) -> list[str]:
        return list(PERMISSION_ACTIONS)

    def policies(self) -> list[str]:
        return [p.value for p in AccessPolicy]

    def permissions(self, *, limit: int = 100) -> dict[str, Any]:
        items = self._repo.list_permissions(limit=limit)
        return {
            "items": [r.as_dict() for r in items],
            "total": len(items),
            "subjects": sorted({r.subject for r in items}),
            "actions": list(PERMISSION_ACTIONS),
        }

    def access_rules(self, *, limit: int = 100) -> dict[str, Any]:
        items = self._repo.list_access_rules(limit=limit)
        return {"items": [r.as_dict() for r in items], "total": len(items)}


class GovernanceCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: GovernanceRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsGovernanceRepository(self._cms)
        self._bus = event_bus or get_event_bus()

    def grant_permission(
        self,
        *,
        subject: str,
        actions: Iterable[str],
        scope_node_id: str = "",
        include_descendants: bool = True,
        note: str = "",
        actor: str,
    ) -> PermissionRule:
        candidate = PermissionRule(
            rule_id="",
            subject=subject,
            actions=tuple(actions),
            scope_node_id=scope_node_id,
            include_descendants=include_descendants,
            note=note,
        )
        errors = candidate.validate()
        if errors:
            raise ValueError("; ".join(errors))

        stored = self._cms.grant_content_permission(
            subject=subject,
            actions=list(actions),
            scope_node_id=scope_node_id,
            include_descendants=include_descendants,
            note=note,
            updated_by=actor,
        )
        self._bus.publish(
            ArcHubDomainEvent(
                event_type="governance.permission.granted",
                aggregate_id=stored.rule_id,
                actor=actor,
                metadata={"subject": stored.subject, "actions": list(stored.actions)},
            )
        )
        return PermissionRule(
            rule_id=stored.rule_id,
            subject=stored.subject,
            actions=tuple(stored.actions),
            scope_node_id=stored.scope_node_id,
            include_descendants=stored.include_descendants,
            note=stored.note,
        )

    def set_access_rule(
        self,
        *,
        node_id: str,
        policy: str,
        member_groups: Iterable[str] = (),
        include_descendants: bool = True,
        actor: str,
    ) -> AccessRule:
        try:
            parsed_policy = AccessPolicy(policy)
        except ValueError as exc:
            raise ValueError(f"unknown access policy: {policy}") from exc

        self._cms.set_public_access_rule(
            node_id=node_id,
            policy=parsed_policy.value,
            member_groups=list(member_groups),
            include_descendants=include_descendants,
            updated_by=actor,
        )
        rule = self._repo.get_access_rule(node_id, inherited=False)
        self._bus.publish(
            ArcHubDomainEvent(
                event_type="governance.access.updated",
                aggregate_id=node_id,
                actor=actor,
                metadata={"policy": parsed_policy.value},
            )
        )
        return rule or AccessRule(
            node_id=node_id, policy=parsed_policy, member_groups=tuple(member_groups)
        )


class AccessControlService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        repository: GovernanceRepository | None = None,
        plugin_host: Any | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._repo = repository or CmsGovernanceRepository(self._cms)
        self._plugin_host = plugin_host

    def identity(self, request: Any) -> Any | None:
        """Resolve identity through auth plugins (None if unauthenticated)."""
        if self._plugin_host is None:
            return None
        return self._plugin_host.authenticate(request)

    def can_perform(self, *, username: str, is_admin: bool, action: str, node_id: str = "") -> bool:
        return self._cms.can_user_perform(
            username=username, is_admin=is_admin, action=action, node_id=node_id
        )

    def can_access(
        self, node_id: str, *, authenticated: bool, groups: Iterable[str] = ()
    ) -> dict[str, Any]:
        rule = self._repo.get_access_rule(node_id, inherited=True)
        if rule is None:
            return {"node_id": node_id, "policy": "public", "allowed": True}
        allowed = rule.permits(authenticated=authenticated, groups=groups)
        return {"node_id": node_id, "policy": rule.policy.value, "allowed": allowed}


def get_archub_governance_query_service(
    *, cms: ArcHubCMSService | None = None, repository: GovernanceRepository | None = None
) -> GovernanceQueryService:
    return GovernanceQueryService(repository or CmsGovernanceRepository(cms))
