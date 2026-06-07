"""Health check subsystem: each bounded context registers a health probe
that the platform queries to produce a combined health report.

Mirrors Wiki.js /healthz and Confluence's /rest/api/1.0/status patterns.
"""

from __future__ import annotations

__all__ = ["HealthCheckResult", "HealthCheckService", "get_health_check_service"]

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HealthCheckResult:
    """Outcome of a single health probe."""

    name: str
    healthy: bool
    message: str = ""
    latency_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "message": self.message,
            "latency_ms": self.latency_ms,
        }


HealthProbe = Callable[[], HealthCheckResult]


class HealthCheckService:
    """Collects and runs health probes from all registered contexts."""

    def __init__(self) -> None:
        self._probes: dict[str, HealthProbe] = {}

    def register(self, name: str, probe: HealthProbe) -> None:
        self._probes[name] = probe

    def check(self) -> dict[str, Any]:
        results: list[HealthCheckResult] = []
        for name, probe in sorted(self._probes.items()):
            try:
                results.append(probe())
            except Exception as exc:
                results.append(HealthCheckResult(name=name, healthy=False, message=str(exc)))
        all_healthy = all(r.healthy for r in results)
        return {
            "status": "healthy" if all_healthy else "degraded",
            "checks": [r.as_dict() for r in results],
            "total": len(results),
            "healthy_count": sum(1 for r in results if r.healthy),
        }

    def probe_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._probes))


_SERVICE: HealthCheckService | None = None


def get_health_check_service() -> HealthCheckService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = HealthCheckService()
    return _SERVICE
