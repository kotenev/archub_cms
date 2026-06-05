"""The PluginHost: discover → permission-check → load → wire enabled plugins."""

from __future__ import annotations

__all__ = ["LoadedPlugin", "PluginHost", "get_plugin_host"]

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from archub_cms.application.plugins import ArcHubPluginRegistry, get_archub_plugin_registry
from archub_cms.domain.plugins import KnowledgePluginManifest
from archub_cms.extensibility.bus import HookLog
from archub_cms.extensibility.config_store import PluginConfigStore
from archub_cms.extensibility.extension_points import (
    AuthExt,
    EventHookExt,
    ExporterExt,
    ImporterExt,
    LLMToolExt,
    MacroExt,
    NotificationExt,
    PluginContext,
    RendererExt,
    SearchExt,
    SearchHit,
    StorageExt,
)
from archub_cms.extensibility.loaders import PluginLoadError, select_loader
from archub_cms.extensibility.permissions import PermissionDenied, PermissionGate
from archub_cms.infrastructure.db.database import Database
from archub_cms.kernel.events import EventBus, get_event_bus
from archub_cms.settings import ArcHubSettings

logger = logging.getLogger("archub_cms.plugins")

_EXECUTABLE_RUNTIMES = {"python", "http", "external"}
# Macro token syntax: {{ name key=value key2="quoted value" }}
_MACRO_RE = re.compile(r"{{\s*([a-zA-Z][\w-]*)((?:\s+[^}]*)?)}}")
_MACRO_ARG_RE = re.compile(r"([a-zA-Z_][\w-]*)=(\"[^\"]*\"|'[^']*'|\S+)")


def _parse_macro_args(raw: str) -> dict[str, Any]:
    args: dict[str, Any] = {}
    for match in _MACRO_ARG_RE.finditer(raw or ""):
        value = match.group(2)
        if value[:1] in {'"', "'"} and value[-1:] == value[:1]:
            value = value[1:-1]
        args[match.group(1)] = value
    return args


def _ext_name(ext: Any) -> str:
    return str(getattr(ext, "name", None) or type(ext).__name__)


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
        self._renderers: list[RendererExt] = []
        self._macros: dict[str, MacroExt] = {}
        self._importers: dict[str, ImporterExt] = {}
        self._exporters: dict[str, ExporterExt] = {}
        self._auth_exts: list[AuthExt] = []
        self._storage: dict[str, StorageExt] = {}
        self._notifiers: dict[str, NotificationExt] = {}
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
            if isinstance(ext, MacroExt):
                self._macros[ext.macro_name] = ext
            # RendererExt is checked after MacroExt because a macro is not a
            # whole-body renderer; the two protocols are distinct by method.
            if isinstance(ext, RendererExt):
                self._renderers.append(ext)
            if isinstance(ext, ImporterExt):
                self._importers[_ext_name(ext)] = ext
            if isinstance(ext, ExporterExt):
                self._exporters[_ext_name(ext)] = ext
            if isinstance(ext, AuthExt):
                self._auth_exts.append(ext)
            if isinstance(ext, StorageExt):
                self._storage[_ext_name(ext)] = ext
            if isinstance(ext, NotificationExt):
                self._notifiers[ext.channel] = ext
                self._bus.subscribe("*", ext.notify)

    # -- accessors ---------------------------------------------------------

    def plugin_instance(self, plugin_id: str) -> Any | None:
        for record in self._loaded:
            if record.manifest.plugin_id == plugin_id:
                return record.instance
        return None

    @property
    def search_extensions(self) -> tuple[SearchExt, ...]:
        return tuple(self._search_exts)

    @property
    def llm_tools(self) -> dict[str, LLMToolExt]:
        return dict(self._llm_tools)

    @property
    def macros(self) -> dict[str, MacroExt]:
        return dict(self._macros)

    @property
    def importers(self) -> dict[str, ImporterExt]:
        return dict(self._importers)

    @property
    def exporters(self) -> dict[str, ExporterExt]:
        return dict(self._exporters)

    def search(self, query: str, *, limit: int = 10) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for ext in self._search_exts:
            try:
                hits.extend(ext.search(query, limit=limit))
            except Exception:  # one plugin must not break search
                logger.exception("search extension failed")
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def render(self, body: str, *, context: dict[str, Any] | None = None) -> str:
        """Run all whole-body renderers in sequence, then expand `{{macro}}`s."""
        ctx = context or {}
        text = body
        for renderer in self._renderers:
            try:
                text = renderer.render(text, context=ctx)
            except Exception:  # a renderer must not break content delivery
                logger.exception("renderer extension failed")
        if self._macros:
            text = _MACRO_RE.sub(self._expand_macro, text)
        return text

    def _expand_macro(self, match: re.Match[str]) -> str:
        name = match.group(1)
        macro = self._macros.get(name)
        if macro is None:
            return match.group(0)  # leave unknown macros untouched
        try:
            return macro.expand(_parse_macro_args(match.group(2)))
        except Exception:  # a macro must not break rendering
            logger.exception("macro %s failed", name)
            return match.group(0)

    @property
    def storage_backends(self) -> dict[str, StorageExt]:
        return dict(self._storage)

    @property
    def notification_channels(self) -> dict[str, NotificationExt]:
        return dict(self._notifiers)

    def storage(self, name: str) -> StorageExt | None:
        return self._storage.get(name)

    def authenticate(self, request: Any) -> Any | None:
        """Resolve an identity through auth plugins; first non-None wins."""
        for ext in self._auth_exts:
            try:
                identity = ext.authenticate(request)
            except Exception:  # an auth plugin must not break the request
                logger.exception("auth extension failed")
                continue
            if identity is not None:
                return identity
        return None

    def run_tool(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._llm_tools.get(name)
        if tool is None:
            raise KeyError(f"no LLM tool named {name!r}")
        return tool.run(arguments)

    def import_documents(self, importer: str, source: Any) -> list[dict[str, Any]]:
        ext = self._importers.get(importer)
        if ext is None:
            raise KeyError(f"no importer named {importer!r}")
        return ext.import_documents(source)

    def export_documents(self, exporter: str, documents: list[dict[str, Any]]) -> Any:
        ext = self._exporters.get(exporter)
        if ext is None:
            raise KeyError(f"no exporter named {exporter!r}")
        return ext.export_documents(documents)

    def report(self) -> dict[str, Any]:
        catalog = self._registry.catalog()
        return {
            "loaded": [item.as_dict() for item in self._loaded],
            "loaded_total": len(self._loaded),
            "failures": list(self._failures),
            "event_hooks": len(self._event_hooks),
            "search_extensions": len(self._search_exts),
            "llm_tools": sorted(self._llm_tools),
            "renderers": len(self._renderers),
            "macros": sorted(self._macros),
            "importers": sorted(self._importers),
            "exporters": sorted(self._exporters),
            "auth_providers": len(self._auth_exts),
            "storage_backends": sorted(self._storage),
            "notification_channels": sorted(self._notifiers),
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
