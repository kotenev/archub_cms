"""Governance and access-control application service for ArcHub CMS."""

from __future__ import annotations

__all__ = [
    "GovernanceOperationResult",
    "ArcHubGovernanceService",
    "get_archub_governance_service",
]

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from archub_cms.domain.events import ArcHubDomainEvent
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


@dataclass(frozen=True)
class GovernanceOperationResult:
    """Result envelope for permissions and public access use cases."""

    payload: dict[str, Any]
    events: tuple[ArcHubDomainEvent, ...] = ()
    status_code: int = 200

    def as_dict(self, *, include_events: bool = False) -> dict[str, Any]:
        if not include_events:
            return self.payload
        return {
            **self.payload,
            "events": [event.as_dict() for event in self.events],
        }


class ArcHubGovernanceService:
    """Application boundary for editor permissions and public access policies."""

    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def has_any_editor_permission(self, username: str) -> bool:
        return self._cms.has_any_content_permission(username)

    def can_user_perform(
        self,
        *,
        username: str,
        is_admin: bool,
        action: str,
        node_id: str = "",
    ) -> bool:
        return self._cms.can_user_perform(
            username=username,
            is_admin=is_admin,
            action=action,
            node_id=node_id,
        )

    def permissions_report(
        self,
        *,
        subject: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        if subject.strip():
            items = self._cms.list_content_permissions(subject=subject, limit=limit)
            return {
                "actions": list(self._cms.available_permission_actions()),
                "items": [item.__dict__ for item in items],
                "total": len(items),
            }
        return self._cms.content_permissions_report(limit=limit)

    def grant_permission(
        self,
        *,
        subject: str,
        actions: Iterable[str],
        scope_node_id: str = "",
        include_descendants: bool = True,
        note: str = "",
        actor: str,
        rule_id: str = "",
    ) -> GovernanceOperationResult:
        rule = self._cms.grant_content_permission(
            subject=subject,
            scope_node_id=scope_node_id,
            actions=actions,
            include_descendants=include_descendants,
            note=note,
            updated_by=actor,
            rule_id=rule_id,
        )
        return GovernanceOperationResult(
            payload=rule.__dict__,
            events=(
                ArcHubDomainEvent(
                    event_type="governance.permission.granted",
                    aggregate_id=rule.rule_id,
                    actor=actor,
                    metadata={
                        "subject": rule.subject,
                        "scope_node_id": rule.scope_node_id,
                        "actions": list(rule.actions),
                        "include_descendants": rule.include_descendants,
                    },
                ),
            ),
        )

    def revoke_permission(self, rule_id: str, *, actor: str) -> GovernanceOperationResult:
        revoked = self._cms.revoke_content_permission(rule_id, revoked_by=actor)
        return GovernanceOperationResult(
            payload={"ok": revoked, "rule_id": rule_id},
            events=(
                ArcHubDomainEvent(
                    event_type="governance.permission.revoked",
                    aggregate_id=rule_id,
                    actor=actor,
                    metadata={"revoked": revoked},
                ),
            ),
            status_code=200 if revoked else 404,
        )

    def public_access_report(self, *, limit: int = 100) -> dict[str, Any]:
        return self._cms.public_access_report(limit=limit)

    def available_public_access_policies(self) -> tuple[str, ...]:
        return self._cms.available_public_access_policies()

    def public_access_rule(self, node_id: str, *, inherited: bool = True) -> dict[str, Any]:
        rule = self._cms.get_public_access_rule(node_id, inherited=inherited)
        return rule.__dict__ if rule is not None else {"policy": "public"}

    def set_public_access_rule(
        self,
        node_id: str,
        *,
        policy: str,
        member_groups: Iterable[str] = (),
        include_descendants: bool = True,
        login_path: str = "/login",
        denied_path: str = "",
        note: str = "",
        actor: str,
    ) -> GovernanceOperationResult:
        rule = self._cms.set_public_access_rule(
            node_id,
            policy=policy,
            member_groups=member_groups,
            include_descendants=include_descendants,
            login_path=login_path,
            denied_path=denied_path,
            note=note,
            updated_by=actor,
        )
        payload = rule.__dict__ if rule is not None else {"node_id": node_id, "policy": "public"}
        return GovernanceOperationResult(
            payload=payload,
            events=(
                ArcHubDomainEvent(
                    event_type="governance.public_access.updated",
                    aggregate_id=node_id,
                    actor=actor,
                    metadata={
                        "policy": payload.get("policy", "public"),
                        "member_groups": list(payload.get("member_groups", ())),
                        "include_descendants": payload.get("include_descendants", True),
                    },
                ),
            ),
        )

    def remove_public_access_rule(self, node_id: str, *, actor: str) -> GovernanceOperationResult:
        removed = self._cms.remove_public_access_rule(node_id, updated_by=actor)
        return GovernanceOperationResult(
            payload={"ok": removed, "node_id": node_id, "policy": "public"},
            events=(
                ArcHubDomainEvent(
                    event_type="governance.public_access.removed",
                    aggregate_id=node_id,
                    actor=actor,
                    metadata={"removed": removed},
                ),
            ),
            status_code=200 if removed else 404,
        )

    def can_access_public_content(
        self,
        node_id: str,
        *,
        username: str = "",
        authenticated: bool = False,
        member_groups: Iterable[str] = (),
    ) -> bool:
        return self._cms.can_access_public_content(
            node_id,
            username=username,
            authenticated=authenticated,
            member_groups=member_groups,
        )


def get_archub_governance_service(
    cms: ArcHubCMSService | None = None,
) -> ArcHubGovernanceService:
    return ArcHubGovernanceService(cms=cms)
