"""The ``AccessRule`` aggregate and public-access decision logic."""

from __future__ import annotations

__all__ = ["AccessPolicy", "AccessRule"]

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AccessPolicy(StrEnum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    MEMBERS = "members"


@dataclass(frozen=True)
class AccessRule:
    """A node's public-access policy and the decision it encodes."""

    node_id: str
    policy: AccessPolicy
    member_groups: tuple[str, ...] = ()
    include_descendants: bool = True
    login_path: str = ""
    denied_path: str = ""
    note: str = ""

    def permits(self, *, authenticated: bool, groups: Iterable[str] = ()) -> bool:
        """Decide whether a visitor may access content under this rule."""
        if self.policy is AccessPolicy.PUBLIC:
            return True
        if self.policy is AccessPolicy.AUTHENTICATED:
            return authenticated
        # MEMBERS: must be authenticated and (no group gate, or in a member group).
        if not authenticated:
            return False
        if not self.member_groups:
            return True
        visitor_groups = {g.strip().casefold() for g in groups if g.strip()}
        return bool(visitor_groups & {g.casefold() for g in self.member_groups})

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "policy": self.policy.value,
            "member_groups": list(self.member_groups),
            "include_descendants": self.include_descendants,
            "login_path": self.login_path,
            "denied_path": self.denied_path,
            "note": self.note,
        }
