"""Plugin manifest registry for ArcHub knowledge platform extensions."""

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
    source = settings or ArcHubSettings.from_env()
    if plugin_dirs is None:
        plugin_dirs = source.plugin_dirs
    return ArcHubPluginRegistry(plugin_dirs=plugin_dirs)


def _builtin_plugins() -> tuple[KnowledgePluginManifest, ...]:
    specs = (
        ("archub.auth.host", "Host Auth Bridge", "auth", "Host-provided editor/member identity."),
        (
            "archub.storage.sqlite",
            "SQLite Content Store",
            "storage",
            "Embedded content tree and versions.",
        ),
        ("archub.renderer.jinja", "Jinja Renderer", "renderer", "Server-rendered public pages."),
        (
            "archub.search.lexical",
            "Lexical Search",
            "search",
            "Token scoring over published content.",
        ),
        (
            "archub.llm.extractive",
            "Offline Extractive LLM",
            "llm_provider",
            "No-network grounded answers.",
        ),
        (
            "archub.llm.openai-compatible",
            "OpenAI Compatible LLM",
            "llm_provider",
            "Cloud or local chat completions endpoint.",
        ),
        (
            "archub.sync.runtime",
            "Runtime Snapshot Sync",
            "sync",
            "Published runtime export for external consumers.",
        ),
        (
            "archub.import.markdown",
            "Markdown Importer",
            "importer",
            "Markdown file ingestion into knowledge articles.",
        ),
        (
            "archub.export.vault",
            "Obsidian Vault Export",
            "exporter",
            "Markdown vault export for offline knowledge work.",
        ),
        ("archub.macro.blocks", "Content Builder Macros", "macro", "Structured reusable blocks."),
        (
            "archub.theme.material",
            "Material Docs Theme",
            "theme",
            "MkDocs Material documentation surface.",
        ),
        (
            "archub.automation.maintenance",
            "Maintenance Jobs",
            "automation",
            "Workflow, runtime, webhook maintenance.",
        ),
        (
            "archub.notification.webhook",
            "Webhook Notifications",
            "notification",
            "Signed outbound events.",
        ),
        (
            "archub.analytics.health",
            "Content Health Analytics",
            "analytics",
            "Model and content quality reports.",
        ),
        (
            "archub.governance.rbac",
            "Governance RBAC",
            "governance",
            "Scoped editor permissions and public access.",
        ),
        (
            "archub.compliance.audit",
            "Audit Trail",
            "compliance",
            "Activity rows and integration events.",
        ),
        (
            "archub.editor.builder",
            "Structured Editor",
            "editor",
            "Schema and block-driven authoring.",
        ),
        (
            "archub.workflow.publish",
            "Publishing Workflow",
            "workflow",
            "Draft, publish, schedule, restore.",
        ),
        (
            "archub.connector.rag",
            "RAG Connector",
            "connector",
            "RAG corpus registry and rebuild hook.",
        ),
    )
    return tuple(
        KnowledgePluginManifest(
            plugin_id=plugin_id,
            name=name,
            version="1.0.0",
            capability=capability,
            description=description,
            provider="archub",
            runtime="host",
            enabled_by_default=True,
            source="builtin",
        )
        for plugin_id, name, capability, description in specs
    )
