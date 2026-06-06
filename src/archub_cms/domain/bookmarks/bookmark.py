"""Bookmark and BookmarkFolder domain models."""

from __future__ import annotations

__all__ = ["Bookmark", "BookmarkFolder"]

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Bookmark:
    """A user's bookmark of a content node."""

    bookmark_id: str
    username: str
    node_id: str
    folder_id: str = ""
    note: str = ""
    created_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "bookmark_id": self.bookmark_id,
            "username": self.username,
            "node_id": self.node_id,
            "folder_id": self.folder_id,
            "note": self.note,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class BookmarkFolder:
    """A named folder grouping a user's bookmarks."""

    folder_id: str
    username: str
    name: str
    parent_folder_id: str = ""
    sort_order: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "folder_id": self.folder_id,
            "username": self.username,
            "name": self.name,
            "parent_folder_id": self.parent_folder_id,
            "sort_order": self.sort_order,
        }
