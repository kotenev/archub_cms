"""Plugin manifest registry for ArcHub platform extensions."""

from __future__ import annotations

__all__ = [
    "ArcHubPluginRegistry",
    "get_archub_plugin_registry",
]

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from archub_cms.domain.plugins import PLUGIN_CAPABILITIES, KnowledgePluginManifest
from archub_cms.settings import ArcHubSettings


class ArcHubPluginRegistry:
    """Safe manifest-driven plugin catalog.

    The registry mirrors Wiki.js/Obsidian/Forge-style manifest discovery but
    deliberately does not import or execute plugin code. Hosts can later bind
    validated manifests to sandboxed workers, HTTP tools, or trusted Python
    entrypoints.
    """

    def __init__(
        self,
        *,
        plugin_dirs: Iterable[Path | str] = (),
        builtins: Iterable[KnowledgePluginManifest] | None = None,
    ) -> None:
        self._plugin_dirs = tuple(Path(item) for item in plugin_dirs)
        self._builtins = tuple(builtins) if builtins is not None else _builtin_plugins()

    def catalog(self, *, include_disabled: bool = True) -> dict[str, Any]:
        manifests, invalid = self._load_manifests()
        plugins = [*self._builtins, *manifests]
        if not include_disabled:
            plugins = [item for item in plugins if item.enabled_by_default]
        plugins.sort(key=lambda item: (item.capability, item.name.casefold(), item.plugin_id))
        capability_counts = dict.fromkeys(PLUGIN_CAPABILITIES, 0)
        for plugin in plugins:
            capability_counts[plugin.capability] = capability_counts.get(plugin.capability, 0) + 1
        return {
            "capabilities": list(PLUGIN_CAPABILITIES),
            "capability_counts": capability_counts,
            "plugins": [item.as_dict() for item in plugins],
            "total": len(plugins),
            "invalid_manifests": invalid,
            "plugin_dirs": [str(item) for item in self._plugin_dirs],
        }

    def manifests(self) -> tuple[KnowledgePluginManifest, ...]:
        """All valid manifests (builtins + discovered files) as domain objects.

        Used by the extensibility runtime to instantiate plugins; the dict-based
        ``catalog`` stays the read model for APIs/UIs.
        """
        file_manifests, _ = self._load_manifests()
        return (*self._builtins, *file_manifests)

    def by_capability(self, capability: str) -> dict[str, Any]:
        clean = capability.strip()
        items = [
            item
            for item in (self._builtins + self._load_manifests()[0])
            if item.capability == clean
        ]
        return {
            "capability": clean,
            "items": [item.as_dict() for item in items],
            "total": len(items),
        }

    def _load_manifests(self) -> tuple[tuple[KnowledgePluginManifest, ...], list[dict[str, Any]]]:
        manifests: list[KnowledgePluginManifest] = []
        invalid: list[dict[str, Any]] = []
        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists():
                continue
            manifest_paths = sorted(
                {
                    *plugin_dir.rglob("plugin.json"),
                    *plugin_dir.rglob("*.archub-plugin.json"),
                }
            )
            for path in manifest_paths:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("Plugin manifest must be a JSON object")
                    manifest = KnowledgePluginManifest.from_dict(payload, source=str(path))
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    invalid.append({"path": str(path), "error": str(exc)})
                    continue
                errors = manifest.validate()
                if errors:
                    invalid.append({"path": str(path), "errors": list(errors)})
                    continue
                manifests.append(manifest)
        return tuple(manifests), invalid


def get_archub_plugin_registry(
    settings: ArcHubSettings | None = None,
    *,
    plugin_dirs: Iterable[Path | str] | None = None,
) -> ArcHubPluginRegistry:
    source: ArcHubSettings = settings if settings is not None else ArcHubSettings.from_env()
    if plugin_dirs is None:
        configured_dirs = source.plugin_dirs or ()
        return ArcHubPluginRegistry(plugin_dirs=configured_dirs)
    return ArcHubPluginRegistry(plugin_dirs=tuple(plugin_dirs))


def _builtin_plugins() -> tuple[KnowledgePluginManifest, ...]:
    return (
        _core(
            "archub.platform.kernel",
            "ArcHub Platform Kernel",
            "platform_module",
            "Shared kernel primitives: events, result, UoW, mediator, saga and health.",
            "archub-core",
            provides=("kernel", "events", "mediator", "saga"),
        ),
        _core(
            "archub.cms.core",
            "ArcHub CMS Core",
            "cms",
            "Content tree, modeling, publishing, delivery and runtime export core.",
            "archub-cms-core",
            provides=("content", "modeling", "publishing", "delivery", "runtime"),
        ),
        _core(
            "archub.knowledge.spaces",
            "Knowledge Spaces",
            "knowledge",
            "Confluence-style spaces, tags, graph, bookmarks and templates.",
            "archub-knowledge-core",
            provides=("spaces", "tags", "graph", "bookmarks", "templates"),
        ),
        _core(
            "archub.media.assets",
            "Media Assets",
            "media",
            "Managed assets, DAM metadata and blob-store contracts.",
            "archub-media-core",
            provides=("media.assets", "media.dam", "media.blob_store"),
        ),
        _core(
            "archub.collaboration.threads",
            "Collaboration Threads",
            "collaboration",
            "Threaded comments, mentions and reactions.",
            "archub-collaboration-core",
            provides=("comments.threads", "mentions", "reactions"),
        ),
        _core(
            "archub.collaboration.live-edit",
            "Live Edit",
            "live_edit",
            "Presence and conflict detection for collaborative editing.",
            "archub-collaboration-core",
            provides=("live_edit.presence", "live_edit.conflict_detection"),
        ),
        _core(
            "archub.adapter.sqlite",
            "SQLite Content Store Adapter",
            "adapter",
            "Embedded SQLite adapter for content, versions, permissions and search state.",
            "archub-adapters",
            provides=("storage.sqlite", "repository.sqlite"),
        ),
        _core(
            "archub.adapter.plugin-store",
            "Plugin Store Adapter",
            "adapter",
            "SQLite/PostgreSQL adapter boundary for executable plugins.",
            "archub-adapters",
            provides=("plugin.store", "plugin.audit"),
        ),
        _core(
            "archub.rest.platform",
            "Platform REST API",
            "rest_api",
            "Rust-first REST module contract mirrored by the current FastAPI surface.",
            "archub-rest-api",
            provides=("api.platform", "api.plugins", "api.modules"),
        ),
        _core(
            "archub.auth.host",
            "Host Auth Bridge",
            "auth",
            "Host-provided editor/member identity.",
            "archub-core",
            provides=("auth.port",),
        ),
        _core(
            "archub.renderer.jinja",
            "Jinja Renderer",
            "renderer",
            "Server-rendered public pages.",
            "archub-core",
            provides=("rendering",),
        ),
        _core(
            "archub.search.lexical",
            "Lexical Search",
            "search",
            "Token scoring over published content.",
            "archub-search-core",
            provides=("search.lexical", "search.facets", "search.index"),
        ),
        _core(
            "archub.llm.extractive",
            "Offline Extractive LLM",
            "llm_provider",
            "No-network grounded answers.",
            "archub-llm-core",
            provides=("llm.offline", "llm.grounded_answers"),
        ),
        _core(
            "archub.llm.openai-compatible",
            "OpenAI Compatible LLM",
            "llm_provider",
            "Cloud or local chat completions endpoint.",
            "archub-llm-core",
            provides=("llm.online", "llm.chat_completions"),
        ),
        _core(
            "archub.sync.runtime",
            "Runtime Snapshot Sync",
            "sync",
            "Published runtime export for external consumers.",
            "archub-cms-core",
            provides=("runtime.snapshot",),
        ),
        _core(
            "archub.import.markdown",
            "Markdown Importer",
            "importer",
            "Markdown file ingestion into knowledge articles.",
            "archub-cms-core",
            provides=("import.markdown",),
        ),
        _core(
            "archub.export.vault",
            "Obsidian Vault Export",
            "exporter",
            "Markdown vault export for offline knowledge work.",
            "archub-cms-core",
            provides=("export.vault",),
        ),
        _core(
            "archub.macro.blocks",
            "Content Builder Macros",
            "macro",
            "Structured reusable blocks.",
            "archub-cms-core",
            provides=("macro.blocks",),
        ),
        _core(
            "archub.theme.material",
            "Material Docs Theme",
            "theme",
            "MkDocs Material documentation surface.",
            "archub-core",
            provides=("theme.material",),
        ),
        _core(
            "archub.automation.maintenance",
            "Maintenance Jobs",
            "automation",
            "Workflow, runtime, webhook maintenance.",
            "archub-automation-core",
            provides=("jobs.maintenance", "jobs.scheduler"),
        ),
        _core(
            "archub.notification.webhook",
            "Webhook Notifications",
            "notification",
            "Signed outbound events.",
            "archub-automation-core",
            provides=("notification.webhook", "notification.signed_delivery"),
        ),
        _core(
            "archub.analytics.health",
            "Content Health Analytics",
            "analytics",
            "Model and content quality reports.",
            "archub-automation-core",
            provides=("analytics.health", "analytics.quality_score"),
        ),
        _core(
            "archub.governance.rbac",
            "Governance RBAC",
            "governance",
            "Scoped editor permissions and public access.",
            "archub-governance-core",
            provides=("governance.rbac", "governance.itil_roles"),
        ),
        _core(
            "archub.compliance.audit",
            "Audit Trail",
            "compliance",
            "Activity rows and integration events.",
            "archub-governance-core",
            provides=("audit.trail", "audit.immutable_log"),
        ),
        _core(
            "archub.editor.builder",
            "Structured Editor",
            "editor",
            "Schema and block-driven authoring.",
            "archub-cms-core",
            provides=("editor.builder",),
        ),
        _core(
            "archub.workflow.publish",
            "Publishing Workflow",
            "workflow",
            "Draft, publish, schedule, restore.",
            "archub-workflow-core",
            provides=("workflow.publish", "workflow.approval", "workflow.schedule"),
        ),
        _core(
            "archub.connector.rag",
            "RAG Connector",
            "connector",
            "RAG corpus registry and rebuild hook.",
            "archub-llm-core",
            provides=("connector.rag", "rag.index_rebuild"),
        ),
    )


def _core(
    plugin_id: str,
    name: str,
    capability: str,
    description: str,
    rust_crate: str,
    *,
    provides: tuple[str, ...] = (),
) -> KnowledgePluginManifest:
    return KnowledgePluginManifest(
        plugin_id=plugin_id,
        name=name,
        version="1.0.0",
        capability=capability,
        description=description,
        provider="archub",
        runtime="rust",
        enabled_by_default=True,
        source="builtin",
        core=True,
        language="rust",
        rust_crate=rust_crate,
        provides=provides,
    )
