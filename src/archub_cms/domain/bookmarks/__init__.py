"""Bookmarks / favorites bounded context: user bookmark management.

Users can bookmark content nodes for quick access (Confluence-style stars,
Obsidian-style favorites). Bookmarks are organized per-user with optional
folders and ordering.
"""

from __future__ import annotations

from archub_cms.domain.bookmarks.bookmark import Bookmark, BookmarkFolder
from archub_cms.domain.bookmarks.repository import BookmarkRepository

__all__ = [
    "Bookmark",
    "BookmarkFolder",
    "BookmarkRepository",
]
