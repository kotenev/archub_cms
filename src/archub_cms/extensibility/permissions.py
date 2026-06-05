"""Manifest permission enforcement for plugins.

Plugins declare ``permissions`` in their manifest. The gate refuses to load a
plugin requesting a permission outside the host's allowlist. ``None`` means
"allow all" (single-tenant trusted deployments); enterprise hosts pass an
explicit allowlist.
"""

from __future__ import annotations

__all__ = ["KNOWN_PERMISSIONS", "PermissionDenied", "PermissionGate"]

from collections.abc import Iterable

KNOWN_PERMISSIONS = (
    "content:read",
    "content:write",
    "content:publish",
    "media:read",
    "media:write",
    "search:read",
    "llm:invoke",
    "events:subscribe",
    "network:outbound",
    "settings:read",
)


class PermissionDenied(Exception):
    """Raised when a plugin requests a permission outside the allowlist."""


class PermissionGate:
    def __init__(self, allowed: Iterable[str] | None = None) -> None:
        # None => allow all. Otherwise restrict to the provided set.
        self._allowed: set[str] | None = None if allowed is None else set(allowed)

    def permits(self, permission: str) -> bool:
        if self._allowed is None:
            return True
        return permission in self._allowed

    def check(self, permissions: Iterable[str]) -> tuple[str, ...]:
        """Return the denied permissions (empty tuple == all granted)."""
        return tuple(p for p in permissions if not self.permits(p))

    def enforce(self, plugin_id: str, permissions: Iterable[str]) -> None:
        denied = self.check(permissions)
        if denied:
            raise PermissionDenied(
                f"plugin {plugin_id} requested denied permissions: {', '.join(denied)}"
            )
