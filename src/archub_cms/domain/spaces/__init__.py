"""Spaces bounded context: Confluence-style knowledge spaces with settings.

A Space is a top-level container that groups related content (Confluence-style
space with home page, permissions, theme, and metadata). Spaces provide
isolation and customization per organizational unit.
"""

from __future__ import annotations

from archub_cms.domain.spaces.repository import SpaceRepository
from archub_cms.domain.spaces.space import Space, SpaceSettings

__all__ = [
    "Space",
    "SpaceRepository",
    "SpaceSettings",
]
