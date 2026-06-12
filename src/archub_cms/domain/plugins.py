"""Domain models for safe plugin manifests and capability discovery."""

from __future__ import annotations

__all__ = [
    "PLUGIN_CAPABILITIES",
    "KnowledgePluginManifest",
]

import re
from dataclasses import dataclass, field
from typing import Any

PLUGIN_CAPABILITIES = (
    "auth",
    "storage",
    "renderer",
    "search",
    "search_indexer",
    "llm_provider",
    "llm_tool",
    "sync",
    "importer",
    "import_format",
    "exporter",
    "export_format",
    "macro",
    "theme",
    "automation",
    "notification",
    "analytics",
    "analytics_provider",
    "governance",
    "compliance",
    "security_policy",
    "editor",
    "workflow",
    "workflow_action",
    "connector",
    "content_transformer",
    "scheduler",
    "cache",
    "chat_handler",
    "dashboard_widget",
    "live_edit",
    "page_action",
    "cms",
    "adapter",
    "rest_api",
    "platform_module",
)
_PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?$")


@dataclass(frozen=True)
class KnowledgePluginManifest:
    """Declarative plugin contract; ArcHub discovers it but does not execute code."""

    plugin_id: str
    name: str
    version: str
    capability: str
    entrypoint: str = ""
    description: str = ""
    provider: str = ""
    runtime: str = "manifest"
    permissions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    settings_schema: dict[str, Any] = field(default_factory=dict)
    enabled_by_default: bool = False
    source: str = "builtin"
    core: bool = False
    language: str = "python"
    rust_crate: str = ""
    provides: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not _PLUGIN_ID_RE.fullmatch(self.plugin_id):
            errors.append("plugin_id must match [a-z][a-z0-9_.-]{2,127}")
        if not self.name.strip():
            errors.append("name is required")
        if not _SEMVER_RE.fullmatch(self.version):
            errors.append("version must use semantic versioning")
        if self.capability not in PLUGIN_CAPABILITIES:
            errors.append(f"unknown capability: {self.capability}")
        if self.runtime not in {"manifest", "python", "http", "external", "host", "rust"}:
            errors.append(f"unknown runtime: {self.runtime}")
        if self.core and self.runtime == "rust" and not self.rust_crate.strip():
            errors.append("rust core plugins must declare rust_crate")
        return tuple(errors)

    @property
    def valid(self) -> bool:
        return not self.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "capability": self.capability,
            "entrypoint": self.entrypoint,
            "description": self.description,
            "provider": self.provider,
            "runtime": self.runtime,
            "permissions": list(self.permissions),
            "tags": list(self.tags),
            "settings_schema": dict(self.settings_schema),
            "enabled_by_default": self.enabled_by_default,
            "source": self.source,
            "core": self.core,
            "language": self.language,
            "rust_crate": self.rust_crate,
            "provides": list(self.provides),
            "valid": self.valid,
            "errors": list(self.validate()),
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        *,
        source: str = "manifest",
    ) -> KnowledgePluginManifest:
        return cls(
            plugin_id=str(payload.get("id") or payload.get("plugin_id") or "").strip(),
            name=str(payload.get("name") or "").strip(),
            version=str(payload.get("version") or "0.0.0").strip(),
            capability=str(payload.get("capability") or "").strip(),
            entrypoint=str(payload.get("entrypoint") or "").strip(),
            description=str(payload.get("description") or "").strip(),
            provider=str(payload.get("provider") or "").strip(),
            runtime=str(payload.get("runtime") or "manifest").strip(),
            permissions=tuple(str(item) for item in payload.get("permissions", ()) if str(item)),
            tags=tuple(str(item) for item in payload.get("tags", ()) if str(item)),
            settings_schema=(
                dict(payload.get("settings_schema") or {})
                if isinstance(payload.get("settings_schema"), dict)
                else {}
            ),
            enabled_by_default=bool(payload.get("enabled_by_default", False)),
            source=source,
            core=bool(payload.get("core", False)),
            language=str(payload.get("language") or "python").strip() or "python",
            rust_crate=str(payload.get("rust_crate") or "").strip(),
            provides=tuple(str(item) for item in payload.get("provides", ()) if str(item)),
        )
