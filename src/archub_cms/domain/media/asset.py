"""The ``MediaAsset`` aggregate."""

from __future__ import annotations

__all__ = ["MediaAsset"]

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MediaAsset:
    """A managed media asset reference (metadata; bytes live in StorageExt)."""

    asset_id: str
    filename: str
    content_type: str
    url: str = ""
    original_name: str = ""
    folder: str = ""
    alt_text: str = ""
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    created_by: str = ""

    @property
    def kind(self) -> str:
        """High-level media kind derived from the content type."""
        major = self.content_type.split("/", 1)[0].casefold()
        if major in {"image", "video", "audio"}:
            return major
        if self.content_type in {"application/pdf", "text/markdown", "text/plain"}:
            return "document"
        return "file"

    def is_allowed(self, allowed_content_types: Iterable[str]) -> bool:
        allowed = {c.strip().casefold() for c in allowed_content_types}
        return not allowed or self.content_type.casefold() in allowed

    def validate(self, *, allowed_content_types: Iterable[str] = ()) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.filename.strip():
            errors.append("filename is required")
        if not self.content_type.strip():
            errors.append("content_type is required")
        elif not self.is_allowed(allowed_content_types):
            errors.append(f"content type not allowed: {self.content_type}")
        return tuple(errors)

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "filename": self.filename,
            "original_name": self.original_name,
            "content_type": self.content_type,
            "kind": self.kind,
            "url": self.url,
            "folder": self.folder,
            "alt_text": self.alt_text,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "created_by": self.created_by,
        }
