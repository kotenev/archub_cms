"""The PluginHost: discover → permission-check → load → wire enabled plugins."""

from __future__ import annotations

__all__ = ["LoadedPlugin", "PluginHost", "get_plugin_host"]

import logging
from dataclasses import dataclass, field
from typing import Any

from archub_cms.application.plugins import ArcHubPluginRegistry, get_archub_plugin_registry
from archub_cms.domain.plugins import KnowledgePluginManifest
from archub_cms.extensibility.bus import HookLog
from archub_cms.extensibility.config_store import PluginConfigStore
from archub_cms.extensibility.extension_points import (
    EventHookExt,
    LLMToolExt,
    PluginContext,
    SearchExt,
    SearchHit,
)
from archub_cms.extensibility.loaders import PluginLoadError, select_loader
from archub_cms.extensibility.permissions import PermissionDenied, PermissionGate
from archub_cms.infrastructure.db.database import Database
from archub_cms.kernel.events import EventBus, get_event_bus
from archub_cms.settings import ArcHubSettings

logger = logging.getLogger("archub_cms.plugins")

_EXECUTABLE_RUNTIMES = {"python", "http", "external"}


@dataclass
class LoadedPlugin:
    manifest: KnowledgePluginManifest
    instance: Any
    extensions: list[Any] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.manifest.plugin_id,
            "name": self.manifest.name,
            "capability": self.manifest.capability,
            "runtime": self.manifest.runtime,
            "extensions": [type(ext).__name__ for ext in self.extensions],
        }


class PluginHost:
    """Owns the lifecycle of executable plugins for one database/process."""

    def __init__(
        self,
        *,
        registry: ArcHubPluginRegistry | None = None,
        config_store: PluginConfigStore | None = None,
        event_bus: EventBus | None = None,
        permission_gate: PermissionGate | None = None,
        settings: ArcHubSettings | None = None,
    ) -> None:
        self._settings = settings or ArcHubSettings.from_env()
        self._registry = registry or get_archub_plugin_registry(self._settings)
        self._config = config_store or PluginConfigStore(Database(self._settings.cms_db_path))
        self._bus = event_bus or get_event_bus()
        self._gate = permission_gate or PermissionGate(None)
        self._hook_log = HookLog(self._bus)

        self._loaded: list[LoadedPlugin] = []
        self._failures: list[dict[str, str]] = []
        self._event_hooks: list[EventHookExt] = []
        self._search_exts: list[SearchExt] = []
        self._llm_tools: dict[str, LLMToolExt] = {}
        self._loaded_ids: set[str] = set()

    # -- lifecycle ---------------------------------------------------------

    def load(self) -> PluginHost:
        for manifest in self._registry.manifests():
            if manifest.runtime not in _EXECUTABLE_RUNTIMES:
                continue  # declarative capability advert (runtime="host"/"manifest")
            if manifest.plugin_id in self._loaded_ids:
                continue
            if not self._config.is_enabled(manifest.plugin_id, default=manifest.enabled_by_default):
                continue
            self._load_one(manifest)
        return self

    def _load_one(self, manifest: KnowledgePluginManifest) -> None:
        try:
            self._gate.enforce(manifest.plugin_id, manifest.permissions)
            loader = select_loader(manifest)
            instance = loader.load(manifest)
        except (PermissionDenied, PluginLoadError) as exc:
            logger.warning("plugin %s not loaded: %s", manifest.plugin_id, exc)
            self._failures.append({"plugin_id": manifest.plugin_id, "error": str(exc)})
            return

        context = PluginContext(
            manifest=manifest,
            settings=self._config.get_settings(manifest.plugin_id),
            event_bus=self._bus,
        )
        setup = getattr(instance, "setup", None)
        if callable(setup):
            try:
                setup(context)
            except Exception as exc:  # isolate plugin setup failures
                logger.exception("plugin %s setup failed", manifest.plugin_id)
                self._failures.append({"plugin_id": manifest.plugin_id, "error": str(exc)})
                return
            extensions = list(context.registered)
        else:
            extensions = [instance]

        record = LoadedPlugin(manifest=manifest, instance=instance, extensions=extensions)
        self._loaded.append(record)
        self._loaded_ids.add(manifest.plugin_id)
        self._classify(extensions)

    def _classify(self, extensions: list[Any]) -> None:
        for ext in extensions:
            if isinstance(ext, EventHookExt):
                self._event_hooks.append(ext)
                for event_type in ext.event_types:
                    self._bus.subscribe(event_type, ext.handle)
            if isinstance(ext, SearchExt):
                self._search_exts.append(ext)
            if isinstance(ext, LLMToolExt):
                self._llm_tools[ext.name] = ext

    # -- accessors ---------------------------------------------------------

    @property
    def search_extensions(self) -> tuple[SearchExt, ...]:
        return tuple(self._search_exts)

    @property
    def llm_tools(self) -> dict[str, LLMToolExt]:
        return dict(self._llm_tools)

    def search(self, query: str, *, limit: int = 10) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for ext in self._search_exts:
            try:
                hits.extend(ext.search(query, limit=limit))
            except Exception:  # one plugin must not break search
                logger.exception("search extension failed")
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def report(self) -> dict[str, Any]:
        catalog = self._registry.catalog()
        return {
            "loaded": [item.as_dict() for item in self._loaded],
            "loaded_total": len(self._loaded),
            "failures": list(self._failures),
            "event_hooks": len(self._event_hooks),
            "search_extensions": len(self._search_exts),
            "llm_tools": sorted(self._llm_tools),
            "hook_counts": self._hook_log.counts,
            "recent_hooks": self._hook_log.recent(),
            "catalog_total": catalog["total"],
            "capability_counts": catalog["capability_counts"],
        }


_HOST: PluginHost | None = None


def get_plugin_host(*, reload: bool = False, settings: ArcHubSettings | None = None) -> PluginHost:
    """Return the process-wide PluginHost, loading plugins on first use."""
    global _HOST
    host = _HOST
    if host is None or reload:
        host = PluginHost(settings=settings).load()
        _HOST = host
    return host
