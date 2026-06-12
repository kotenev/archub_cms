"""Space and SpaceSettings domain models."""

from __future__ import annotations

__all__ = ["Space", "SpaceSettings"]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SpaceSettings:
    """Per-space configuration overrides."""

    icon: str = ""
    color: str = "#0B7285"
    default_content_type: str = "page"
    allow_comments: bool = True
    allow_reactions: bool = True
    theme: str = "default"
    custom_styles: str = ""
    sidebar_items: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "icon": self.icon,
            "color": self.color,
            "default_content_type": self.default_content_type,
            "allow_comments": self.allow_comments,
            "allow_reactions": self.allow_reactions,
            "theme": self.theme,
            "custom_styles": self.custom_styles,
            "sidebar_items": list(self.sidebar_items),
        }


@dataclass(frozen=True)
class Space:
    """A Confluence-style knowledge space."""

    space_key: str
    name: str
    description: str = ""
    root_node_id: str = ""
    owner: str = ""
    visibility: str = "public"
    settings: SpaceSettings = field(default_factory=SpaceSettings)
    tags: tuple[str, ...] = ()
    document_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "space_key": self.space_key,
            "name": self.name,
            "description": self.description,
            "root_node_id": self.root_node_id,
            "owner": self.owner,
            "visibility": self.visibility,
            "settings": self.settings.as_dict(),
            "tags": list(self.tags),
            "document_count": self.document_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
