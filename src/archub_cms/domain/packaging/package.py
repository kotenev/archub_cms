"""The ``ContentPackage`` value object and ``PackageInspection`` read model."""

from __future__ import annotations

__all__ = ["PACKAGE_SCHEMA_VERSION", "ContentPackage", "PackageInspection"]

from dataclasses import dataclass, field
from typing import Any

PACKAGE_SCHEMA_VERSION = "archub.package.v1"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class ContentPackage:
    """A portable, schema-versioned content bundle (immutable view over a dict)."""

    data: dict[str, Any] = field(default_factory=dict)

    @property
    def schema_version(self) -> str:
        return str(self.data.get("schema_version") or "")

    @property
    def name(self) -> str:
        return str(self.data.get("name") or "ArcHub package")

    @property
    def description(self) -> str:
        return str(self.data.get("description") or "")

    @property
    def package_id(self) -> str:
        return str(self.data.get("package_id") or "")

    @property
    def is_supported(self) -> bool:
        return self.schema_version == PACKAGE_SCHEMA_VERSION

    def summary(self) -> dict[str, int]:
        content = _as_dict(self.data.get("content"))
        model = _as_dict(self.data.get("content_model"))
        return {
            "nodes": len(_as_list(content.get("nodes"))),
            "content_types": len(_as_list(model.get("content_types"))),
            "data_types": len(_as_list(model.get("data_types"))),
            "templates": len(_as_list(model.get("templates"))),
            "media_assets": len(_as_list(self.data.get("media_assets"))),
            "redirects": len(_as_list(self.data.get("redirects"))),
            "dictionary_items": len(_as_list(self.data.get("dictionary_items"))),
            "workflows": len(_as_list(self.data.get("workflows"))),
            "public_access": len(_as_list(self.data.get("public_access"))),
            "domains": len(_as_list(self.data.get("domains"))),
        }

    @property
    def is_empty(self) -> bool:
        return all(count == 0 for count in self.summary().values())

    def as_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "name": self.name,
            "description": self.description,
            "schema_version": self.schema_version,
            "is_supported": self.is_supported,
            "summary": self.summary(),
        }


@dataclass(frozen=True)
class PackageInspection:
    """Outcome of validating a package before import."""

    ok: bool
    issues: tuple[dict[str, str], ...] = ()
    counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> PackageInspection:
        return cls(
            ok=bool(result.get("ok")),
            issues=tuple(result.get("issues") or ()),
            counts=dict(result.get("counts") or {}),
        )

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.get("severity") == "error")

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_count": self.error_count,
            "issues": list(self.issues),
            "counts": dict(self.counts),
        }
