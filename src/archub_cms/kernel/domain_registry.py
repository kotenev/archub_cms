"""Domain registry: a simple service locator for bounded-context domain services.

Each bounded context registers its domain services here during startup; the
registry provides type-safe lookups without introducing circular imports
between contexts.
"""

from __future__ import annotations

__all__ = ["DomainRegistry", "get_domain_registry"]

from typing import Any


class DomainRegistry:
    """Lightweight service registry keyed by (context, role)."""

    def __init__(self) -> None:
        self._services: dict[tuple[str, str], Any] = {}

    def register(self, context: str, role: str, service: Any) -> None:
        self._services[(context, role)] = service

    def get(self, context: str, role: str) -> Any | None:
        return self._services.get((context, role))

    def require(self, context: str, role: str) -> Any:
        svc = self.get(context, role)
        if svc is None:
            raise LookupError(f"no service registered for {context!r}/{role!r}")
        return svc

    def context_names(self) -> tuple[str, ...]:
        return tuple(sorted({ctx for ctx, _ in self._services}))

    def registered_count(self) -> int:
        return len(self._services)

    def snapshot(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for ctx, role in self._services:
            result.setdefault(ctx, []).append(role)
        return result


_REGISTRY: DomainRegistry | None = None


def get_domain_registry() -> DomainRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = DomainRegistry()
    return _REGISTRY
