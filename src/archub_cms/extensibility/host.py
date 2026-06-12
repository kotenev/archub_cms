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
    AnalyticsProviderExt,
    AuthExt,
    ChatHandlerExt,
    ConnectorExt,
    ContentTransformerExt,
    DashboardWidgetExt,
    EditorExt,
    EventHookExt,
    ExporterExt,
    ExportFormatExt,
    ImporterExt,
    ImportFormatExt,
    LiveEditExt,
    LLMToolExt,
    MacroExt,
    NotificationExt,
    PageActionExt,
    PluginContext,
    RendererExt,
    ScheduledJobExt,
    SearchExt,
    SearchHit,
    SearchIndexerExt,
    SecurityPolicyExt,
    StorageExt,
    ThemeExt,
    WorkflowActionExt,
)
from archub_cms.extensibility.loaders import PluginLoadError, select_loader
from archub_cms.extensibility.permissions import PermissionDenied, PermissionGate
from archub_cms.extensibility.platform_adapter import PluginAuditLog, PluginPlatformAdapter
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
        audit_log: PluginAuditLog | None = None,
    ) -> None:
        self._settings = settings or ArcHubSettings.from_env()
        self._database = Database(self._settings.cms_db_path)
        self._registry = registry or get_archub_plugin_registry(self._settings)
        self._audit = audit_log or PluginAuditLog(self._database)
        self._config = config_store or PluginConfigStore(self._database, audit_log=self._audit)
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
        self._themes: dict[str, ThemeExt] = {}
        self._scheduled_jobs: dict[str, ScheduledJobExt] = {}
        self._analytics_providers: dict[str, AnalyticsProviderExt] = {}
        self._workflow_actions: dict[str, WorkflowActionExt] = {}
        self._content_transformers: dict[str, ContentTransformerExt] = {}
        self._search_indexers: dict[str, SearchIndexerExt] = {}
        self._security_policies: dict[str, SecurityPolicyExt] = {}
        self._editors: dict[str, EditorExt] = {}
        self._connectors: dict[str, ConnectorExt] = {}
        self._chat_handlers: dict[str, ChatHandlerExt] = {}
        self._dashboard_widgets: dict[str, DashboardWidgetExt] = {}
        self._export_formats: dict[str, ExportFormatExt] = {}
        self._import_formats: dict[str, ImportFormatExt] = {}
        self._live_edit_providers: dict[str, LiveEditExt] = {}
        self._page_actions: dict[str, PageActionExt] = {}
        self._loaded_ids: set[str] = set()
        self._extension_platforms: dict[int, PluginPlatformAdapter] = {}

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
        platform = PluginPlatformAdapter(
            plugin_id=manifest.plugin_id,
            settings=self._settings,
            audit_log=self._audit,
        )
        platform.audit(
            "plugin.load.attempt",
            target=manifest.entrypoint,
            metadata={"runtime": manifest.runtime, "capability": manifest.capability},
        )
        try:
            self._gate.enforce(manifest.plugin_id, manifest.permissions)
            loader = select_loader(manifest)
            instance = loader.load(manifest)
        except (PermissionDenied, PluginLoadError) as exc:
            logger.warning("plugin %s not loaded: %s", manifest.plugin_id, exc)
            platform.audit(
                "plugin.load.failed",
                target=manifest.entrypoint,
                metadata={"error": str(exc), "error_type": type(exc).__name__},
            )
            self._failures.append({"plugin_id": manifest.plugin_id, "error": str(exc)})
            return

        context = PluginContext(
            manifest=manifest,
            settings=self._config.get_settings(manifest.plugin_id),
            event_bus=self._bus,
            platform=platform,
        )
        setup = getattr(instance, "setup", None)
        if callable(setup):
            try:
                platform.audit("plugin.setup.attempt")
                setup(context)
            except Exception as exc:  # isolate plugin setup failures
                logger.exception("plugin %s setup failed", manifest.plugin_id)
                platform.audit(
                    "plugin.setup.failed",
                    metadata={"error": str(exc), "error_type": type(exc).__name__},
                )
                self._failures.append({"plugin_id": manifest.plugin_id, "error": str(exc)})
                return
            extensions = list(context.registered)
        else:
            extensions = [instance]

        record = LoadedPlugin(manifest=manifest, instance=instance, extensions=extensions)
        self._loaded.append(record)
        self._loaded_ids.add(manifest.plugin_id)
        for extension in extensions:
            self._extension_platforms[id(extension)] = platform
        self._classify(extensions)
        platform.audit(
            "plugin.loaded",
            metadata={"extensions": [type(ext).__name__ for ext in extensions]},
        )

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
            if isinstance(ext, ThemeExt):
                self._themes[ext.theme_id] = ext
            if isinstance(ext, ScheduledJobExt):
                self._scheduled_jobs[ext.job_name] = ext
            if isinstance(ext, AnalyticsProviderExt):
                self._analytics_providers[ext.provider_name] = ext
                self._bus.subscribe("*", ext.track)
            if isinstance(ext, WorkflowActionExt):
                self._workflow_actions[ext.action_name] = ext
            if isinstance(ext, ContentTransformerExt):
                self._content_transformers[ext.transformer_name] = ext
            if isinstance(ext, SearchIndexerExt):
                self._search_indexers[ext.indexer_name] = ext
            if isinstance(ext, SecurityPolicyExt):
                self._security_policies[ext.policy_name] = ext
            if isinstance(ext, EditorExt):
                self._editors[ext.editor_id] = ext
            if isinstance(ext, ConnectorExt):
                self._connectors[ext.connector_id] = ext
            if isinstance(ext, ChatHandlerExt):
                self._chat_handlers[ext.handler_id] = ext
            if isinstance(ext, DashboardWidgetExt):
                self._dashboard_widgets[ext.widget_type] = ext
            if isinstance(ext, ExportFormatExt):
                self._export_formats[ext.format_id] = ext
            if isinstance(ext, ImportFormatExt):
                self._import_formats[ext.format_id] = ext
            if isinstance(ext, LiveEditExt):
                self._live_edit_providers[ext.provider_id] = ext
            if isinstance(ext, PageActionExt):
                self._page_actions[ext.action_id] = ext

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
    def audit_log(self) -> PluginAuditLog:
        return self._audit

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
                extension_hits = ext.search(query, limit=limit)
                hits.extend(extension_hits)
                self._audit_extension(
                    ext,
                    "search.query",
                    metadata={"query": query, "limit": limit, "hits": len(extension_hits)},
                )
            except Exception:  # one plugin must not break search
                logger.exception("search extension failed")
                self._audit_extension(ext, "search.query.failed", metadata={"query": query})
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def render(self, body: str, *, context: dict[str, Any] | None = None) -> str:
        """Run all whole-body renderers in sequence, then expand `{{macro}}`s."""
        ctx = context or {}
        text = body
        for renderer in self._renderers:
            try:
                text = renderer.render(text, context=ctx)
                self._audit_extension(renderer, "renderer.render")
            except Exception:  # a renderer must not break content delivery
                logger.exception("renderer extension failed")
                self._audit_extension(renderer, "renderer.render.failed")
        if self._macros:
            text = _MACRO_RE.sub(self._expand_macro, text)
        return text

    def _expand_macro(self, match: re.Match[str]) -> str:
        name = match.group(1)
        macro = self._macros.get(name)
        if macro is None:
            return match.group(0)  # leave unknown macros untouched
        try:
            expanded = macro.expand(_parse_macro_args(match.group(2)))
            self._audit_extension(macro, "macro.expand", target=name)
            return expanded
        except Exception:  # a macro must not break rendering
            logger.exception("macro %s failed", name)
            self._audit_extension(macro, "macro.expand.failed", target=name)
            return match.group(0)

    @property
    def storage_backends(self) -> dict[str, StorageExt]:
        return dict(self._storage)

    @property
    def notification_channels(self) -> dict[str, NotificationExt]:
        return dict(self._notifiers)

    @property
    def themes(self) -> dict[str, ThemeExt]:
        return dict(self._themes)

    @property
    def scheduled_job_extensions(self) -> dict[str, ScheduledJobExt]:
        return dict(self._scheduled_jobs)

    @property
    def analytics_providers(self) -> dict[str, AnalyticsProviderExt]:
        return dict(self._analytics_providers)

    @property
    def workflow_actions(self) -> dict[str, WorkflowActionExt]:
        return dict(self._workflow_actions)

    @property
    def content_transformers(self) -> dict[str, ContentTransformerExt]:
        return dict(self._content_transformers)

    @property
    def search_indexers(self) -> dict[str, SearchIndexerExt]:
        return dict(self._search_indexers)

    @property
    def security_policies(self) -> dict[str, SecurityPolicyExt]:
        return dict(self._security_policies)

    @property
    def editors(self) -> dict[str, EditorExt]:
        return dict(self._editors)

    @property
    def connectors(self) -> dict[str, ConnectorExt]:
        return dict(self._connectors)

    @property
    def chat_handlers(self) -> dict[str, ChatHandlerExt]:
        return dict(self._chat_handlers)

    @property
    def dashboard_widgets(self) -> dict[str, DashboardWidgetExt]:
        return dict(self._dashboard_widgets)

    @property
    def export_formats(self) -> dict[str, ExportFormatExt]:
        return dict(self._export_formats)

    @property
    def import_formats(self) -> dict[str, ImportFormatExt]:
        return dict(self._import_formats)

    @property
    def live_edit_providers(self) -> dict[str, LiveEditExt]:
        return dict(self._live_edit_providers)

    @property
    def page_actions(self) -> dict[str, PageActionExt]:
        return dict(self._page_actions)

    def transform_content(
        self, content: dict[str, Any], *, phase: str = "render"
    ) -> dict[str, Any]:
        for transformer in self._content_transformers.values():
            if transformer.phase == phase:
                try:
                    content = transformer.transform(content)
                except Exception:
                    logger.exception("content transformer %s failed", transformer.transformer_name)
        return content

    def check_security_publish(self, content: dict[str, Any]) -> tuple[bool, str]:
        for policy in self._security_policies.values():
            allowed, reason = policy.check_publish(content)
            if not allowed:
                return False, f"{policy.policy_name}: {reason}"
        return True, ""

    def check_security_access(self, user: Any, content: dict[str, Any]) -> tuple[bool, str]:
        for policy in self._security_policies.values():
            allowed, reason = policy.check_access(user, content)
            if not allowed:
                return False, f"{policy.policy_name}: {reason}"
        return True, ""

    def storage(self, name: str) -> StorageExt | None:
        return self._storage.get(name)

    def authenticate(self, request: Any) -> Any | None:
        """Resolve an identity through auth plugins; first non-None wins."""
        for ext in self._auth_exts:
            try:
                identity = ext.authenticate(request)
                self._audit_extension(ext, "auth.authenticate")
            except Exception:  # an auth plugin must not break the request
                logger.exception("auth extension failed")
                self._audit_extension(ext, "auth.authenticate.failed")
                continue
            if identity is not None:
                return identity
        return None

    def run_tool(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._llm_tools.get(name)
        if tool is None:
            raise KeyError(f"no LLM tool named {name!r}")
        try:
            result = tool.run(arguments)
        except Exception:
            self._audit_extension(tool, "llm_tool.run.failed", target=name)
            raise
        self._audit_extension(tool, "llm_tool.run", target=name)
        return result

    def import_documents(self, importer: str, source: Any) -> list[dict[str, Any]]:
        ext = self._importers.get(importer)
        if ext is None:
            raise KeyError(f"no importer named {importer!r}")
        try:
            documents = ext.import_documents(source)
        except Exception:
            self._audit_extension(ext, "importer.run.failed", target=importer)
            raise
        self._audit_extension(
            ext,
            "importer.run",
            target=importer,
            metadata={"documents": len(documents)},
        )
        return documents

    def export_documents(self, exporter: str, documents: list[dict[str, Any]]) -> Any:
        ext = self._exporters.get(exporter)
        if ext is None:
            raise KeyError(f"no exporter named {exporter!r}")
        try:
            exported = ext.export_documents(documents)
        except Exception:
            self._audit_extension(ext, "exporter.run.failed", target=exporter)
            raise
        self._audit_extension(
            ext,
            "exporter.run",
            target=exporter,
            metadata={"documents": len(documents)},
        )
        return exported

    def _audit_extension(
        self,
        extension: Any,
        action: str,
        *,
        target: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        platform = self._extension_platforms.get(id(extension))
        if platform is not None:
            platform.audit(action, target=target, metadata=metadata)

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
            "themes": sorted(self._themes),
            "scheduled_jobs": sorted(self._scheduled_jobs),
            "analytics_providers": sorted(self._analytics_providers),
            "workflow_actions": sorted(self._workflow_actions),
            "content_transformers": sorted(self._content_transformers),
            "search_indexers": sorted(self._search_indexers),
            "security_policies": sorted(self._security_policies),
            "editors": sorted(self._editors),
            "connectors": sorted(self._connectors),
            "chat_handlers": sorted(self._chat_handlers),
            "dashboard_widgets": sorted(self._dashboard_widgets),
            "export_formats": sorted(self._export_formats),
            "import_formats": sorted(self._import_formats),
            "live_edit_providers": sorted(self._live_edit_providers),
            "page_actions": sorted(self._page_actions),
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
