"""Example analytics provider plugin demonstrating AnalyticsProviderExt."""

from __future__ import annotations

from typing import Any

from archub_cms.extensibility.extension_points import AnalyticsProviderExt


class ConsoleAnalyticsPlugin:
    """Logs analytics events to stdout (demonstrates AnalyticsProviderExt)."""

    def setup(self, context: Any) -> None:
        context.register(ConsoleAnalyticsProvider())


class ConsoleAnalyticsProvider(AnalyticsProviderExt):
    provider_name = "console-analytics"

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def track(self, event: Any) -> None:
        self._events.append(
            {
                "event_type": getattr(event, "event_type", "unknown"),
                "aggregate_id": getattr(event, "aggregate_id", ""),
                "actor": getattr(event, "actor", ""),
            }
        )

    def report(self, *, metric: str, period: str) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for evt in self._events:
            key = evt["event_type"]
            counts[key] = counts.get(key, 0) + 1
        return {
            "metric": metric,
            "period": period,
            "counts": counts,
            "total_events": len(self._events),
        }
