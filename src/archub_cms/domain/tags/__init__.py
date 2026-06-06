"""Tags / taxonomy bounded context: hierarchical categorization.

Manages a taxonomy of tags organized in a tree. Tags can be shared across
content types and spaces (Confluence-style labels, Wiki.js/Obsidian-style
tags). Supports tag hierarchies (parent-child), aliases, and usage counts.
"""

from __future__ import annotations

from archub_cms.domain.tags.repository import TagRepository
from archub_cms.domain.tags.tag import Tag, TagNode

__all__ = [
    "Tag",
    "TagNode",
    "TagRepository",
]
