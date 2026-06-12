"""Plugin lifecycle management — the Wiki.js/Confluence-style plugin admin.

Merges three views into one management catalog: the declarative manifest
registry, the per-plugin config store (enabled + settings), and the live host
(loaded / failed). Enable/disable/configure persist to the config store, reload
the host so the change takes effect immediately, and emit a domain event.
"""

from __future__ import annotations

__all__ = ["PluginManagementService", "get_archub_plugin_management_service"]

from pathlib import Path
from typing import Any

from archub_cms.application.core_plugins import core_plugin_coverage
from archub_cms.application.module_distribution_service import (
    ModuleDistributionBuilder,
    ModuleDistributionInstaller,
    ModuleMarketplaceRepository,
)
from archub_cms.application.plugins import ArcHubPluginRegistry, get_archub_plugin_registry
from archub_cms.extensibility.config_store import PluginConfigStore
from archub_cms.extensibility.host import get_plugin_host
from archub_cms.extensibility.platform_adapter import PluginAuditLog
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
        database = Database(self._settings.cms_db_path)
        self._config = config_store or PluginConfigStore(
            database,
            audit_log=PluginAuditLog(database),
        )
        self._bus = event_bus or get_event_bus()

    def catalog(self) -> dict[str, Any]:
        host = get_plugin_host(settings=self._settings)
        report = host.report()
        loaded = {item["plugin_id"] for item in report["loaded"]}
        failed = {item["plugin_id"]: item["error"] for item in report["failures"]}
        manifests = self._registry.manifests()
        coverage = core_plugin_coverage(manifests)
        available_crates = set(coverage["workspace"]["crate_names"])
        items: list[dict[str, Any]] = []
        for manifest in manifests:
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
                    "version": manifest.version,
                    "core": manifest.core,
                    "language": manifest.language,
                    "rust_crate": manifest.rust_crate,
                    "rust_crate_available": (
                        not manifest.rust_crate or manifest.rust_crate in available_crates
                    ),
                    "provides": list(manifest.provides),
                }
            )
        items.sort(key=lambda item: (item["capability"], item["plugin_id"]))
        return {
            "items": items,
            "total": len(items),
            "loaded_total": len(loaded),
            "capability_counts": report["capability_counts"],
            "install_root": str(self._installer().install_root),
            "rust_workspace": coverage,
        }

    def install_from_file(
        self,
        path: str | Path,
        *,
        actor: str = "",
        enable: bool | None = None,
        replace: bool = False,
        expected_sha256: str = "",
    ) -> dict[str, Any]:
        installed = self._installer().install(
            path,
            replace=replace,
            expected_sha256=expected_sha256,
        )
        plugin_id = str(installed["plugin_id"])
        if enable is not None:
            self._config.set_enabled(plugin_id, enable, updated_by=actor)
        self._reload()
        self._bus.publish(
            ArcHubDomainEvent(
                "plugin.installed",
                plugin_id,
                actor,
                {
                    "source": str(path),
                    "installed_path": installed["installed_path"],
                    "capability": installed["capability"],
                    "runtime": installed["runtime"],
                    "core": installed.get("core", False),
                    "rust_crate": installed.get("rust_crate", ""),
                },
            )
        )
        return {**installed, "status": self.status(plugin_id)}

    def marketplace(self, repository: str | Path) -> dict[str, Any]:
        return ModuleMarketplaceRepository(repository).catalog()

    def build_marketplace(
        self,
        output_root: str | Path,
        *,
        include_builtins: bool = True,
        include_plugins: bool = True,
        replace: bool = True,
    ) -> dict[str, Any]:
        manifests = [
            manifest
            for manifest in self._registry.manifests()
            if (include_builtins or manifest.source != "builtin")
            and (include_plugins or manifest.source == "builtin")
        ]
        return ModuleDistributionBuilder(output_root=output_root, replace=replace).build_all(
            manifests
        )

    def install_from_marketplace(
        self,
        repository: str | Path,
        module_id: str,
        *,
        version: str = "",
        actor: str = "",
        enable: bool | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        marketplace = ModuleMarketplaceRepository(repository)
        item = marketplace.package_for(module_id, version=version)
        source = item.get("source")
        if not source:
            raise ValueError(f"marketplace item {module_id!r} does not declare a package")
        installed = self.install_from_file(
            str(source),
            actor=actor,
            enable=enable,
            replace=replace,
            expected_sha256=str(item.get("sha256") or ""),
        )
        self._bus.publish(
            ArcHubDomainEvent(
                "plugin.marketplace.installed",
                str(installed["plugin_id"]),
                actor,
                {
                    "repository": str(repository),
                    "module_id": module_id,
                    "version": str(item.get("version") or ""),
                },
            )
        )
        return {**installed, "marketplace_item": item}

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

    def _installer(self) -> ModuleDistributionInstaller:
        return ModuleDistributionInstaller(install_roots=self._settings.plugin_dirs)


def get_archub_plugin_management_service(
    *, settings: ArcHubSettings | None = None
) -> PluginManagementService:
    return PluginManagementService(settings=settings)
