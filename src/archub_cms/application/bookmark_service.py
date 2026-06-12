"""Application service for the bookmarks context.

Manages user bookmarks and bookmark folders for quick content access
(Confluence-style stars, Obsidian-style favorites).
"""

from __future__ import annotations

__all__ = ["BookmarkService", "get_archub_bookmark_service"]

import secrets
import time
from typing import Any

from archub_cms.domain.bookmarks.bookmark import Bookmark, BookmarkFolder
from archub_cms.domain.bookmarks.repository import BookmarkRepository


class BookmarkService:
    def __init__(self, *, repository: BookmarkRepository | None = None) -> None:
        self._repo = repository

    def add(
        self, *, username: str, node_id: str, folder_id: str = "", note: str = ""
    ) -> dict[str, Any]:
        if self._repo is None:
            raise RuntimeError("no repository configured")
        existing = self._repo.find(username, node_id)
        if existing is not None:
            return existing.as_dict()
        bookmark = Bookmark(
            bookmark_id=secrets.token_urlsafe(10),
            username=username,
            node_id=node_id,
            folder_id=folder_id,
            note=note,
            created_at=time.time(),
        )
        self._repo.add(bookmark)
        return bookmark.as_dict()

    def remove(self, bookmark_id: str) -> bool:
        if self._repo is None:
            return False
        return self._repo.remove(bookmark_id)

    def list_for_user(self, username: str, *, folder_id: str = "") -> dict[str, Any]:
        if self._repo is None:
            return {"username": username, "items": [], "total": 0}
        bookmarks = self._repo.list_for_user(username, folder_id=folder_id)
        return {
            "username": username,
            "items": [b.as_dict() for b in bookmarks],
            "total": len(bookmarks),
        }

    def folders(self, username: str) -> dict[str, Any]:
        if self._repo is None:
            return {"username": username, "folders": []}
        folders = self._repo.folders(username)
        return {
            "username": username,
            "folders": [f.as_dict() for f in folders],
        }

    def create_folder(
        self, *, username: str, name: str, parent_folder_id: str = ""
    ) -> dict[str, Any]:
        if self._repo is None:
            raise RuntimeError("no repository configured")
        folder = BookmarkFolder(
            folder_id=secrets.token_urlsafe(10),
            username=username,
            name=name,
            parent_folder_id=parent_folder_id,
        )
        self._repo.create_folder(folder)
        return folder.as_dict()


def get_archub_bookmark_service(*, repository: BookmarkRepository | None = None) -> BookmarkService:
    return BookmarkService(repository=repository)
