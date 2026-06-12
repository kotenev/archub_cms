"""Plugin manifest builder for ArcHub SDK users."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?$")


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    capability: str
    runtime: str = "manifest"
    entrypoint: str = ""
    description: str = ""
    provider: str = ""
    permissions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    settings_schema: dict[str, Any] = field(default_factory=dict)
    enabled_by_default: bool = False
    language: str = "python"
    provides: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not _PLUGIN_ID_RE.fullmatch(self.plugin_id):
            errors.append("plugin_id must match [a-z][a-z0-9_.-]{2,127}")
        if not self.name.strip():
            errors.append("name is required")
        if not _SEMVER_RE.fullmatch(self.version):
            errors.append("version must use semantic versioning")
        if self.runtime not in {"manifest", "python", "http", "external", "host", "rust"}:
            errors.append(f"unknown runtime: {self.runtime}")
        if self.runtime in {"http", "external"} and not self.entrypoint:
            errors.append("http/external plugin manifests require entrypoint")
        return tuple(errors)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "capability": self.capability,
            "runtime": self.runtime,
            "entrypoint": self.entrypoint,
            "description": self.description,
            "provider": self.provider,
            "permissions": list(self.permissions),
            "tags": list(self.tags),
            "settings_schema": dict(self.settings_schema),
            "enabled_by_default": self.enabled_by_default,
            "language": self.language,
            "provides": list(self.provides),
        }

    def to_json(self) -> str:
        errors = self.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"
