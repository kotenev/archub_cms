"""Governance bounded context: RBAC permissions + public access policies.

Models the enterprise auth surface — ``PermissionRule`` (a subject granted a set
of actions over a scope) and ``AccessRule`` (a node's public-access policy:
public / authenticated / members). The access *decision* logic lives in the
aggregates (``PermissionRule.grants``, ``AccessRule.permits``) so it is pure and
testable; scope/descendant resolution that needs the tree stays in the service.
"""

from __future__ import annotations

from archub_cms.domain.governance.access import AccessPolicy, AccessRule
from archub_cms.domain.governance.permission import PERMISSION_ACTIONS, PermissionRule
from archub_cms.domain.governance.repository import GovernanceRepository

__all__ = [
    "PERMISSION_ACTIONS",
    "AccessPolicy",
    "AccessRule",
    "GovernanceRepository",
    "PermissionRule",
]
