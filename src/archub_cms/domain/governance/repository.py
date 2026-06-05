"""Repository port for the governance context."""

from __future__ import annotations

__all__ = ["GovernanceRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.governance.access import AccessRule
from archub_cms.domain.governance.permission import PermissionRule


@runtime_checkable
class GovernanceRepository(Protocol):
    def list_permissions(self, *, limit: int = 100) -> list[PermissionRule]: ...

    def list_access_rules(self, *, limit: int = 100) -> list[AccessRule]: ...

    def get_access_rule(self, node_id: str, *, inherited: bool = True) -> AccessRule | None: ...
