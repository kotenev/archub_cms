"""Example plugin: header/token-based authentication (AuthExt).

Demonstrates pluggable identity (the seam SSO/SAML/OIDC plugins would use). It
resolves an :class:`ArcHubUser` from request headers — an API token mapped to a
user+groups, or ``X-ArcHub-User``/``X-ArcHub-Groups`` for trusted gateways. Token
→ identity mappings come from plugin settings, falling back to a demo mapping.
"""

from __future__ import annotations

__all__ = ["HeaderAuthPlugin"]

from typing import Any

from archub_cms.extensibility.extension_points import PluginContext
from archub_cms.ports import ArcHubUser

_DEMO_TOKENS = {
    "demo-admin-token": {"username": "admin", "is_admin": True, "groups": ["staff"]},
    "demo-editor-token": {"username": "editor", "is_admin": False, "groups": ["editors"]},
}


class HeaderAuthPlugin:
    def __init__(self) -> None:
        self._tokens: dict[str, dict[str, Any]] = dict(_DEMO_TOKENS)

    def setup(self, context: PluginContext) -> None:
        configured = context.settings.get("tokens")
        if isinstance(configured, dict):
            self._tokens.update(configured)
        context.register(self)

    def authenticate(self, request: Any) -> ArcHubUser | None:
        headers = _headers(request)
        token = headers.get("authorization", "").removeprefix("Bearer ").strip()
        if token and token in self._tokens:
            mapping = self._tokens[token]
            return ArcHubUser(
                username=str(mapping.get("username") or "user"),
                is_admin=bool(mapping.get("is_admin")),
                groups=tuple(mapping.get("groups") or ()),
            )
        username = headers.get("x-archub-user", "").strip()
        if username:
            groups = tuple(
                g.strip() for g in headers.get("x-archub-groups", "").split(",") if g.strip()
            )
            is_admin = headers.get("x-archub-admin", "").strip().lower() in {"1", "true", "yes"}
            return ArcHubUser(username=username, is_admin=is_admin, groups=groups)
        return None


def _headers(request: Any) -> dict[str, str]:
    raw = getattr(request, "headers", None)
    if raw is None and isinstance(request, dict):
        raw = request.get("headers")
    if raw is None:
        return {}
    try:
        return {str(k).lower(): str(v) for k, v in dict(raw).items()}
    except (TypeError, ValueError):
        return {}
