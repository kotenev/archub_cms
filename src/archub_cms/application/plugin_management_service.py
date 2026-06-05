"""Plugin lifecycle management — the Wiki.js/Confluence-style plugin admin.

Merges three views into one management catalog: the declarative manifest
registry, the per-plugin config store (enabled + settings), and the live host
(loaded / failed). Enable/disable/configure persist to the config store, reload
the host so the change takes effect immediately, and emit a domain event.
"""

from __future__ import annotations

__all__ = ["PluginManagementService", "get_archub_plugin_management_service"]

from typing import Any

from archub_cms.application.plugins import ArcHubPluginRegistry, get_archub_plugin_registry
from archub_cms.extensibility.config_store import PluginConfigStore
from archub_cms.extensibility.host import get_plugin_host
from archub_cms.infrastructure.db.database import Database
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.settings import ArcHubSettings

_EXECUTABLE_RUNTIMES = {"python", "http", "external"}


class PluginManagementService:
    def __init__(
        self,
        *,
        settings: ArcHubSettings | None = None,
        registry: ArcHubPluginRegistry | None = None,
        config_store: PluginConfigStore | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._settings = settings or ArcHubSettings.from_env()
        self._registry = registry or get_archub_plugin_registry(self._settings)
        self._config = config_store or PluginConfigStore(Database(self._settings.cms_db_path))
        self._bus = event_bus or get_event_bus()

    def catalog(self) -> dict[str, Any]:
        host = get_plugin_host(settings=self._settings)
        report = host.report()
        loaded = {item["plugin_id"] for item in report["loaded"]}
        failed = {item["plugin_id"]: item["error"] for item in report["failures"]}
        items: list[dict[str, Any]] = []
        for manifest in self._registry.manifests():
            executable = manifest.runtime in _EXECUTABLE_RUNTIMES
            items.append(
                {
                    "plugin_id": manifest.plugin_id,
                    "name": manifest.name,
                    "capability": manifest.capability,
                    "runtime": manifest.runtime,
                    "executable": executable,
                    "enabled": self._config.is_enabled(
                        manifest.plugin_id, default=manifest.enabled_by_default
                    ),
                    "enabled_by_default": manifest.enabled_by_default,
                    "loaded": manifest.plugin_id in loaded,
                    "error": failed.get(manifest.plugin_id, ""),
                    "settings": self._config.get_settings(manifest.plugin_id),
                    "permissions": list(manifest.permissions),
                }
            )
        items.sort(key=lambda item: (item["capability"], item["plugin_id"]))
        return {
            "items": items,
            "total": len(items),
            "loaded_total": len(loaded),
            "capability_counts": report["capability_counts"],
        }

    def enable(self, plugin_id: str, *, actor: str = "") -> dict[str, Any]:
        return self._set_enabled(plugin_id, True, actor=actor, event="plugin.enabled")

    def disable(self, plugin_id: str, *, actor: str = "") -> dict[str, Any]:
        return self._set_enabled(plugin_id, False, actor=actor, event="plugin.disabled")

    def configure(
        self, plugin_id: str, settings: dict[str, Any], *, actor: str = ""
    ) -> dict[str, Any]:
        self._require(plugin_id)
        self._config.set_settings(plugin_id, settings, updated_by=actor)
        self._reload()
        self._bus.publish(
            ArcHubDomainEvent("plugin.configured", plugin_id, actor, {"keys": sorted(settings)})
        )
        return self.status(plugin_id)

    def status(self, plugin_id: str) -> dict[str, Any]:
        for item in self.catalog()["items"]:
            if item["plugin_id"] == plugin_id:
                return item
        raise KeyError(plugin_id)

    # -- internals ---------------------------------------------------------

    def _set_enabled(
        self, plugin_id: str, enabled: bool, *, actor: str, event: str
    ) -> dict[str, Any]:
        self._require(plugin_id)
        self._config.set_enabled(plugin_id, enabled, updated_by=actor)
        self._reload()
        self._bus.publish(ArcHubDomainEvent(event, plugin_id, actor, {"enabled": enabled}))
        return self.status(plugin_id)

    def _require(self, plugin_id: str) -> None:
        known = {m.plugin_id for m in self._registry.manifests()}
        if plugin_id not in known:
            raise KeyError(f"unknown plugin: {plugin_id}")

    def _reload(self) -> None:
        get_plugin_host(reload=True, settings=self._settings)


def get_archub_plugin_management_service(
    *, settings: ArcHubSettings | None = None
) -> PluginManagementService:
    return PluginManagementService(settings=settings)
